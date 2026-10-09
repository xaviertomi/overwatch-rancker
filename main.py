import json
import math
import os
import time
from collections import defaultdict
from collections.abc import Mapping

import requests

import config
import heroes
from scripts.collection_policy import load_policy


def _record_outcome(collection_report, player_id, gamemode, **outcome):
    if collection_report is not None:
        collection_report.setdefault("outcomes", {})[(player_id, gamemode)] = outcome


def get_player_stats(player_id, gamemode, collection_report=None):
    """Fetch one OverFast career response with bounded transient retries.

    The two-argument call remains compatible with the original pipeline. When a
    report mapping is supplied, it receives the final classification for this
    logical player/mode request.
    """
    url = f"{config.BASE_URL}/{player_id}/stats/career"
    params = {"gamemode": gamemode}
    last_status = None

    for attempt in range(config.MAX_REQUEST_ATTEMPTS):
        try:
            response = requests.get(url, params=params, timeout=config.REQUEST_TIMEOUT)
            last_status = response.status_code
            if response.status_code == 200:
                try:
                    payload = response.json()
                except (ValueError, json.JSONDecodeError):
                    _record_outcome(collection_report, player_id, gamemode,
                                    classification="invalid_responses", status=200)
                    return None
                if isinstance(payload, Mapping):
                    _record_outcome(collection_report, player_id, gamemode,
                                    classification="successful_responses", status=200,
                                    payload=payload)
                    return payload
                _record_outcome(collection_report, player_id, gamemode,
                                classification="invalid_responses", status=200)
                return None

            retryable = response.status_code == 429 or response.status_code >= 500
            if not retryable:
                category = "private_or_unavailable"
                if response.status_code == 403:
                    print(f"    [!] Profil privé pour {player_id}.")
                elif response.status_code == 404:
                    print(f"    [!] Profil introuvable pour {player_id} ({gamemode}).")
                else:
                    print(f"    [!] Erreur API ({response.status_code}) pour {player_id}.")
                _record_outcome(collection_report, player_id, gamemode,
                                classification=category, status=response.status_code)
                return None

            if attempt + 1 < config.MAX_REQUEST_ATTEMPTS:
                time.sleep(config.RETRY_BACKOFF_SECONDS * (2 ** attempt))
                continue
        except requests.RequestException as exc:
            if attempt + 1 < config.MAX_REQUEST_ATTEMPTS:
                time.sleep(config.RETRY_BACKOFF_SECONDS * (2 ** attempt))
                continue
            print(f"    [!] Erreur de connexion : {exc}")
            _record_outcome(collection_report, player_id, gamemode,
                            classification="transient_failures", status=None)
            return None
        except Exception as exc:
            print(f"    [!] Erreur inattendue : {exc}")
            _record_outcome(collection_report, player_id, gamemode,
                            classification="transient_failures", status=last_status)
            return None

    print(f"    [!] Échec transitoire ({last_status}) pour {player_id}.")
    _record_outcome(collection_report, player_id, gamemode,
                    classification="transient_failures", status=last_status)
    return None


def extract_stats(hero_data):
    """Extract totals, reconstructing positive totals from per-10-minute averages."""
    if not isinstance(hero_data, Mapping):
        hero_data = {}
    flat = {}
    avg_data = {}

    for category, content in hero_data.items():
        if category == "average":
            if isinstance(content, list):
                avg_data = {
                    item["key"]: item["value"]
                    for item in content
                    if isinstance(item, Mapping) and "key" in item and "value" in item
                }
            elif isinstance(content, Mapping):
                avg_data = dict(content)
            continue
        if isinstance(content, list):
            for item in content:
                if isinstance(item, Mapping) and "key" in item and "value" in item:
                    flat[item["key"]] = item["value"]
        elif isinstance(content, Mapping):
            flat.update(content)
        else:
            flat[category] = content

    time_played = flat.get("time_played", 0)
    if not isinstance(time_played, (int, float)) or isinstance(time_played, bool):
        time_played = 0
    time_10m = time_played / 600.0 if time_played > 0 else 0

    def get_total_or_reconstruct(keys_total, keys_avg):
        for key in keys_total:
            value = flat.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
                return value
        for key in keys_avg:
            value = avg_data.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
                return value * time_10m
        return 0

    games_won = flat.get("games_won", 0)
    games_played = flat.get("games_played", 0)
    if not isinstance(games_won, (int, float)) or isinstance(games_won, bool):
        games_won = 0
    if not isinstance(games_played, (int, float)) or isinstance(games_played, bool):
        games_played = 0
    if games_played == 0 and games_won > 0:
        games_played = games_won / 0.5

    return {
        "time_played": time_played,
        "games_won": games_won,
        "games_played": games_played,
        "eliminations": get_total_or_reconstruct(["eliminations"], ["eliminations", "eliminations_avg"]),
        "assists": get_total_or_reconstruct(["assists"], ["assists", "assists_avg"]),
        "deaths": get_total_or_reconstruct(["deaths"], ["deaths", "deaths_avg"]),
        "damage_done": get_total_or_reconstruct(
            ["hero_damage_done", "damage_done", "all_damage_done", "damage"],
            ["damage", "hero_damage_done", "damage_avg"],
        ),
        "healing_done": get_total_or_reconstruct(
            ["healing_done", "healing"], ["healing", "healing_done", "healing_avg"]
        ),
    }


def calculate_norm(val, min_v, max_v, is_inv=False):
    """Calculate a clamped relative value between zero and one."""
    if min_v >= max_v:
        return 1.0
    norm = (val - min_v) / (max_v - min_v)
    if is_inv:
        norm = 1.0 - norm
    return max(0.0, min(1.0, norm))


def _hero_container(data, mode):
    if not isinstance(data, Mapping):
        return {}
    if isinstance(data.get("heroes"), Mapping):
        return data["heroes"]
    if isinstance(data.get("heroes_stats"), Mapping):
        return data["heroes_stats"]
    nested = data.get(mode)
    if isinstance(nested, Mapping) and isinstance(nested.get("heroes"), Mapping):
        return nested["heroes"]
    return data


def _empty_report(configured, excluded, outcomes):
    counts = {
        "configured_requests": configured,
        "excluded_requests": excluded,
        "expected_requests": configured - excluded,
        "attempted_requests": len(outcomes),
        "successful_responses": 0,
        "private_or_unavailable": 0,
        "transient_failures": 0,
        "invalid_responses": 0,
    }
    for outcome in outcomes.values():
        category = outcome.get("classification")
        if category in counts:
            counts[category] += 1
    counts["complete"] = (
        counts["attempted_requests"] == counts["expected_requests"]
        and counts["successful_responses"] == counts["expected_requests"]
        and counts["private_or_unavailable"] == 0
        and counts["transient_failures"] == 0
        and counts["invalid_responses"] == 0
    )
    return counts


def main():
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    policy = load_policy(config.COLLECTION_POLICY_PATH)
    excluded_pairs = {(entry["player_id"], entry["gamemode"]) for entry in policy["excluded_requests"]}
    configured = len(config.PLAYERS) * len(config.MODES)
    outcomes = {}
    player_totals = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    player_global_time = defaultdict(float)
    seuil_heures = getattr(config, "MIN_HOURS_THRESHOLD", 0.0)
    print(f"=== DEBUT DU TRAITEMENT (Filtre: {seuil_heures} heures minimum) ===")
    print(f"Requêtes configurées: {configured}; exclues: {len(excluded_pairs)}; éligibles: {configured - len(excluded_pairs)}")

    for player_id in config.PLAYERS:
        pseudo = player_id.split("-")[0]
        print(f"-> Traitement de {pseudo}...")
        for mode in config.MODES:
            if (player_id, mode) in excluded_pairs:
                continue
            data = get_player_stats(player_id, mode, {"outcomes": outcomes})
            if data is None:
                continue
            heroes_data_api = _hero_container(data, mode)
            heroes_found = 0
            mode_total_time = 0
            for hero_key, hero_data in heroes_data_api.items():
                if hero_key not in heroes.HERO_ROLES:
                    continue
                flat = extract_stats(hero_data)
                if flat["time_played"] > 0:
                    heroes_found += 1
                    mode_total_time += flat["time_played"]
                    player_global_time[pseudo] += flat["time_played"]
                    for field in ("time_played", "games_won", "games_played", "eliminations", "assists", "deaths", "healing_done", "damage_done"):
                        player_totals[pseudo][hero_key][field] += flat[field]
            if heroes_found > 0:
                print(f"    [{mode.upper()}] : Fusion de {heroes_found} héros réussie ({round(mode_total_time / 3600, 1)}h accumulées).")
            else:
                print(f"    [{mode.upper()}] : Aucun héros compatible encontrado.")
            if config.REQUEST_DELAY_SECONDS:
                time.sleep(config.REQUEST_DELAY_SECONDS)

    raw_roles_data = {"Tank": defaultdict(list), "Damage": defaultdict(list), "Support": defaultdict(list)}
    for pseudo, heroes_data in player_totals.items():
        for hero, totals in heroes_data.items():
            if totals["time_played"] <= 0:
                continue
            time_hours = totals["time_played"] / 3600
            time_10min = totals["time_played"] / 600
            winrate = min(100.0, totals["games_won"] / totals["games_played"] * 100) if totals["games_played"] > 0 else 0.0
            deaths = totals["deaths"] if totals["deaths"] > 0 else 1
            raw_roles_data[heroes.HERO_ROLES[hero]][hero].append({
                "pseudo": pseudo,
                "Temps_Jeu_Heures": round(time_hours, 2),
                "Winrate_%": round(winrate, 2),
                "KDA": round((totals["eliminations"] + totals["assists"]) / deaths, 2),
                "Elims_Moyenne": round(totals["eliminations"] / time_10min if time_10min > 0 else 0, 2),
                "Assists_Moyenne": round(totals["assists"] / time_10min if time_10min > 0 else 0, 2),
                "Degats_Moyenne": round(totals["damage_done"] / time_10min if time_10min > 0 else 0, 2),
                "Soins_Moyenne": round(totals["healing_done"] / time_10min if time_10min > 0 else 0, 2),
                "Morts_Moyenne": totals["deaths"] / time_10min if time_10min > 0 else 0,
            })

    roles_data = {"Tank": defaultdict(list), "Damage": defaultdict(list), "Support": defaultdict(list)}
    for role, heroes_dict in raw_roles_data.items():
        for hero, players_list in heroes_dict.items():
            players_list.sort(key=lambda item: item["Temps_Jeu_Heures"], reverse=True)
            filtered = [item for item in players_list if item["Temps_Jeu_Heures"] >= seuil_heures]
            if len(filtered) < 2:
                filtered = players_list[:2]
            if filtered:
                roles_data[role][hero] = filtered

    final_json = {"Résumé_Joueurs": {}, "Tank": {}, "Damage": {}, "Support": {}}
    for pseudo, total_time in sorted(player_global_time.items(), key=lambda item: item[1], reverse=True):
        final_json["Résumé_Joueurs"][pseudo] = {"Temps_Jeu_Total_Heures": round(total_time / 3600, 2)}

    for role, heroes_dict in roles_data.items():
        coefs = config.ROLE_CONFIGS[role]
        total_coef = sum(coefs.values())
        for hero, players_list in heroes_dict.items():
            for player in players_list:
                score_total = 0
                for stat_name, coef in coefs.items():
                    if coef == 0 or stat_name not in player:
                        continue
                    values = [item.get(stat_name, 0) for item in players_list]
                    score_total += calculate_norm(player.get(stat_name, 0), min(values), max(values), stat_name in config.INVERTED_METRICS) * coef
                player["score"] = round((score_total / total_coef) * 100, 2) if total_coef > 0 else 0.0
            players_list.sort(key=lambda item: (item["score"], item["Temps_Jeu_Heures"]), reverse=True)
            final_json[role][hero] = [{key: player[key] for key in (
                "pseudo", "score", "Temps_Jeu_Heures", "Winrate_%", "KDA",
                "Elims_Moyenne", "Assists_Moyenne", "Degats_Moyenne", "Soins_Moyenne"
            )} for player in players_list]
        final_json[role] = dict(sorted(final_json[role].items()))

    output_file = os.path.join(config.OUTPUT_DIR, "classement.json")
    with open(output_file, "w", encoding="utf-8") as output:
        json.dump(final_json, output, indent=2, ensure_ascii=False)
    report = _empty_report(configured, len(excluded_pairs), outcomes)
    print(f"\n[SUCCES] JSON généré avec fusion QP+Ranked dans : {output_file}")
    print(f"Rapport collecte: {json.dumps(report, ensure_ascii=False)}")
    return report


if __name__ == "__main__":
    main()
