"""
Model aniqlik tracker — qaysi ob-havo modeli qaysi shahar uchun eng aniq ekanini kuzatadi.

Mantiq:
- Resolved natijalardan (results.json, trades.json) qaysi modellar to'g'ri bashorat qilganini aniqlaydi
- Har bir shahar va model uchun accuracy statistikasini accuracy.json da saqlaydi
- Aniqroq modellar yuqoriroq og'irlik (weight) oladi: 1.0 bazaviy, 2.0 gacha

Modellar:
  Ensemble: gfs, ecmwf, icon, gem, bom
  Deterministic: meteofrance, jma, ukmo, knmi
  Tashqi: nws
"""

import json
import os
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(BASE_DIR, "..", "..")
ACCURACY_FILE = os.path.join(PROJECT_ROOT, "storage", "accuracy.json")
RESULTS_FILE = os.path.join(PROJECT_ROOT, "storage", "results.json")
TRADES_FILE = os.path.join(PROJECT_ROOT, "storage", "trades.json")

ALL_MODELS = [
    "gfs", "ecmwf", "icon", "gem", "bom",
    "meteofrance", "jma", "ukmo", "knmi", "nws",
]

# Weight limits
BASE_WEIGHT = 1.0
MIN_WEIGHT = 0.5
MAX_WEIGHT = 2.0
MIN_TRADES_FOR_WEIGHT = 5  # Kamida 5 ta savdo bo'lmasa bazaviy weight


def load_accuracy() -> dict:
    """accuracy.json ni yuklaydi."""
    if os.path.exists(ACCURACY_FILE):
        try:
            with open(ACCURACY_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_accuracy(data: dict):
    """accuracy.json ga saqlaydi."""
    with open(ACCURACY_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


def load_results() -> list[dict]:
    """results.json ni yuklaydi."""
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def load_trades() -> list[dict]:
    """trades.json ni yuklaydi."""
    if os.path.exists(TRADES_FILE):
        try:
            with open(TRADES_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def update_accuracy(city: str, model: str, was_correct: bool):
    """
    Bitta model natijasini yangilaydi.

    Args:
        city: shahar kaliti (masalan "nyc", "chicago")
        model: model nomi (masalan "gfs", "ecmwf")
        was_correct: model to'g'ri bashorat qildimi
    """
    data = load_accuracy()

    city = city.lower().strip()
    model = model.lower().strip()

    if city not in data:
        data[city] = {}

    if model not in data[city]:
        data[city][model] = {"correct": 0, "total": 0, "accuracy": 0.0}

    entry = data[city][model]
    entry["total"] += 1
    if was_correct:
        entry["correct"] += 1
    entry["accuracy"] = round(entry["correct"] / entry["total"], 4) if entry["total"] > 0 else 0.0

    save_accuracy(data)


def get_model_weights(city: str) -> dict[str, float]:
    """
    Shahar uchun model og'irliklarini qaytaradi.
    Aniqroq modellar yuqoriroq og'irlik oladi (1.0 bazaviy, 0.5-2.0 oralig'ida).

    Agar shahar uchun yetarli ma'lumot bo'lmasa, barcha modellar 1.0 oladi.

    Args:
        city: shahar kaliti

    Returns:
        {"gfs": 1.2, "ecmwf": 1.5, "icon": 1.0, ...}
    """
    data = load_accuracy()
    city = city.lower().strip()
    city_data = data.get(city, {})

    weights = {}
    for model in ALL_MODELS:
        if model in city_data and city_data[model]["total"] >= MIN_TRADES_FOR_WEIGHT:
            acc = city_data[model]["accuracy"]
            # Linear scaling: 0% accuracy = MIN_WEIGHT, 100% accuracy = MAX_WEIGHT
            # 50% accuracy = BASE_WEIGHT
            weight = MIN_WEIGHT + (MAX_WEIGHT - MIN_WEIGHT) * acc
            weight = max(MIN_WEIGHT, min(MAX_WEIGHT, weight))
            weights[model] = round(weight, 3)
        else:
            weights[model] = BASE_WEIGHT

    return weights


def get_accuracy_report() -> str:
    """
    Telegram uchun formatlangan accuracy hisoboti.

    Returns:
        HTML formatlangan matn
    """
    data = load_accuracy()

    if not data:
        return "📊 <b>MODEL ANIQLIK</b>\n\nHali ma'lumot yo'q. Resolved savdolar kerak."

    lines = [
        "📊 <b>MODEL ANIQLIK HISOBOTI</b>",
        f"📅 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]

    for city in sorted(data.keys()):
        city_models = data[city]
        if not city_models:
            continue

        lines.append(f"🏙 <b>{city.upper()}</b>")

        # Model'larni accuracy bo'yicha tartiblash
        sorted_models = sorted(
            city_models.items(),
            key=lambda x: x[1].get("accuracy", 0),
            reverse=True,
        )

        for model, stats in sorted_models:
            acc = stats.get("accuracy", 0)
            correct = stats.get("correct", 0)
            total = stats.get("total", 0)

            if total == 0:
                continue

            # Emoji: yaxshi/o'rta/yomon
            if acc >= 0.7:
                emoji = "🟢"
            elif acc >= 0.4:
                emoji = "🟡"
            else:
                emoji = "🔴"

            weight = get_model_weights(city).get(model, BASE_WEIGHT)
            weight_str = f" (w={weight:.1f})" if total >= MIN_TRADES_FOR_WEIGHT else ""

            lines.append(
                f"  {emoji} {model}: <b>{acc:.0%}</b> "
                f"({correct}/{total}){weight_str}"
            )

        lines.append("")

    # Umumiy eng yaxshi/yomon modellar
    model_totals = {}
    for city_models in data.values():
        for model, stats in city_models.items():
            if model not in model_totals:
                model_totals[model] = {"correct": 0, "total": 0}
            model_totals[model]["correct"] += stats.get("correct", 0)
            model_totals[model]["total"] += stats.get("total", 0)

    if model_totals:
        lines.append("<b>📈 UMUMIY (barcha shaharlar):</b>")
        sorted_overall = sorted(
            model_totals.items(),
            key=lambda x: x[1]["correct"] / x[1]["total"] if x[1]["total"] > 0 else 0,
            reverse=True,
        )
        for model, stats in sorted_overall:
            if stats["total"] == 0:
                continue
            acc = stats["correct"] / stats["total"]
            lines.append(
                f"  {'🟢' if acc >= 0.7 else '🟡' if acc >= 0.4 else '🔴'} "
                f"{model}: <b>{acc:.0%}</b> ({stats['correct']}/{stats['total']})"
            )

    return "\n".join(lines)


def recalculate_from_history():
    """
    accuracy.json ni results.json va trades.json dan qayta hisoblaydi.

    Mantiq:
    - results.json dagi har bir resolved natija uchun:
      - trade ma'lumotidan shahar va per_model_summary ni oladi
      - Har bir modelning bashoratini haqiqiy natija bilan solishtiradi
    - accuracy.json ni noldan qayta yozadi
    """
    results = load_results()
    trades = load_trades()

    # Trade'larni market_id bo'yicha indekslash
    trade_by_mid = {}
    for trade in trades:
        mid = trade.get("market_id")
        if mid:
            trade_by_mid[str(mid)] = trade

    accuracy_data = {}

    for result in results:
        won = result.get("won")
        if won is None:
            continue  # Noaniq natija — o'tkazamiz

        trade = result.get("trade", {})
        city = trade.get("city", "").lower().strip()
        if not city or city == "unknown":
            continue

        # per_model_summary dan modellarni ajratib olish
        # Format: "gfs:75%, ecmwf:90%, icon:50%, ..."
        per_model = trade.get("per_model_summary", "")
        side = trade.get("side", "").upper()

        if not per_model:
            continue

        if city not in accuracy_data:
            accuracy_data[city] = {}

        # Har bir model natijasini tekshirish
        for part in per_model.split(","):
            part = part.strip()
            if ":" not in part:
                continue

            model_name, prob_str = part.split(":", 1)
            model_name = model_name.strip().lower()

            try:
                prob = float(prob_str.strip().replace("%", "")) / 100.0
            except (ValueError, TypeError):
                continue

            if model_name not in accuracy_data[city]:
                accuracy_data[city][model_name] = {"correct": 0, "total": 0, "accuracy": 0.0}

            entry = accuracy_data[city][model_name]
            entry["total"] += 1

            # Model to'g'ri bashorat qildimi?
            # YES savdo yutgan va model yuqori ehtimollik ko'rsatgan
            # NO savdo yutgan va model past ehtimollik ko'rsatgan
            if side == "YES":
                model_agrees = prob >= 0.5
            else:
                model_agrees = prob < 0.5

            # Model rozi bo'lgan va savdo yutgan, YOKI
            # Model rozi bo'lmagan va savdo yutqazgan
            was_correct = (model_agrees == won)

            if was_correct:
                entry["correct"] += 1

    # Accuracy hisoblash
    for city in accuracy_data:
        for model in accuracy_data[city]:
            entry = accuracy_data[city][model]
            entry["accuracy"] = round(
                entry["correct"] / entry["total"], 4
            ) if entry["total"] > 0 else 0.0

    save_accuracy(accuracy_data)

    # Statistika chiqarish
    total_entries = sum(
        sum(s["total"] for s in models.values())
        for models in accuracy_data.values()
    )
    city_count = len(accuracy_data)

    print(f"Accuracy qayta hisoblandi: {city_count} shahar, {total_entries} yozuv")
    return accuracy_data


if __name__ == "__main__":
    print("=" * 55)
    print("  MODEL ACCURACY TRACKER")
    print("=" * 55)

    # 1) Mavjud accuracy ni ko'rsatish
    data = load_accuracy()
    if data:
        print(f"\nMavjud accuracy.json: {len(data)} shahar")
        for city, models in data.items():
            print(f"\n  {city.upper()}:")
            for model, stats in sorted(models.items(), key=lambda x: x[1]["accuracy"], reverse=True):
                print(f"    {model}: {stats['accuracy']:.0%} ({stats['correct']}/{stats['total']})")
    else:
        print("\naccuracy.json topilmadi yoki bo'sh.")

    # 2) Tarixdan qayta hisoblash
    print(f"\n{'=' * 55}")
    print("Tarixdan qayta hisoblash...")
    result = recalculate_from_history()

    if result:
        print(f"\nYangilangan natijalar:")
        for city, models in result.items():
            print(f"\n  {city.upper()}:")
            for model, stats in sorted(models.items(), key=lambda x: x[1]["accuracy"], reverse=True):
                print(f"    {model}: {stats['accuracy']:.0%} ({stats['correct']}/{stats['total']})")

        # 3) Weight'larni ko'rsatish
        print(f"\n{'=' * 55}")
        print("Model og'irliklari:")
        for city in result:
            weights = get_model_weights(city)
            non_default = {m: w for m, w in weights.items() if w != BASE_WEIGHT}
            if non_default:
                print(f"\n  {city.upper()}: {non_default}")
            else:
                print(f"\n  {city.upper()}: barcha modellar bazaviy (1.0)")

        # 4) Telegram hisobot
        print(f"\n{'=' * 55}")
        print("Telegram hisobot:")
        print(get_accuracy_report())
    else:
        print("Qayta hisoblash uchun ma'lumot yo'q.")

    # 5) Demo: update_accuracy
    print(f"\n{'=' * 55}")
    print("Demo: update_accuracy('nyc', 'ecmwf', True)")
    update_accuracy("nyc", "ecmwf", True)
    weights = get_model_weights("nyc")
    print(f"NYC weights: { {m: w for m, w in weights.items() if w != BASE_WEIGHT} or 'barcha 1.0' }")
