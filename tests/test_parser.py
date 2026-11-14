"""Run with: python tests/test_parser.py  (no Home Assistant needed)."""
import importlib.util
import pathlib

_path = pathlib.Path(__file__).parents[1] / "custom_components" / "stashcook" / "parser.py"
_spec = importlib.util.spec_from_file_location("parser", _path)
p = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p)

KIEV = """<b>Quick - oven while Harrison's at swimming (5:30-6:30)</b>
- 4 garlic chicken Kievs
- ~1kg Maris Piper potatoes
- Peas

Roasties: peel and chop potatoes, parboil 8 mins, shake, roast in hot oil 200°C / 180 fan ~45 mins. Kievs in for the last 25-30 mins. Peas on the side.

<b>Tonight:</b> make the Shepherd's Pie for tomorrow (see Tuesday) - make it big, it's Wednesday's lunch too."""

SHEP = """<b>Make ahead Monday night - reheat tonight after orchestra (Charlie 5-7)</b>
Makes enough for dinner + 2 lunches Wednesday.
- 1kg beef mince (2 packs)
- Grated cheddar for the top

Brown mince, add onion and carrot 5 mins, purée, then gravy/stock. Simmer 20 mins. Mash potatoes with butter and milk. Mince in dish, mash on top, cheese over. Fridge.
<b>Reheat:</b> 190°C / 170 fan for 35-40 mins till bubbling."""

SPLIT = """<b>Emma (home):</b> red pepper & tomato soup (Sunday prep) + part-baked baguette, 10 mins in the oven.

<b>Geraint (office day):</b> pack a wrap the night before - tortilla wrap, Greek chicken, salad, tzatziki. Roll tight in foil."""

PREP = """<b>Sunday prep (about 45 mins) - covers lunches Mon, Tue, Thu, Fri</b>

<b>Greek chicken</b>
- 1kg chicken thigh fillets
- Schwartz gyros mix, 1 tbsp oil
Toss thighs in the mix and oil. Roast 200°C / 180 fan for 25-30 mins till cooked through. Cool, slice, fridge in a tub. Keeps 4 days.

<b>Red pepper & tomato soup</b>
- 500g frozen sliced peppers
Soften onions and garlic 5 mins, add peppers 5 mins, add tomatoes and stock, simmer 20 mins, blend. Season. Fridge in 2 tubs (Tue + Fri)."""

LEFT = """<b>3 mins</b>
Leftover Shepherd's Pie from last night. Microwave until piping hot all the way through (3-4 mins, stir halfway). Peas on the side if you fancy."""


def test_titles():
    assert p.slot_for_title("Family Dinner - Chicken Kiev & Roasties") == ("dinner", "Chicken Kiev & Roasties")
    assert p.slot_for_title("Lunch Prep - Greek Chicken & Pepper Soup")[0] == "lunch_prep"
    assert p.slot_for_title("Lunch - Greek Chicken Pittas")[0] == "lunch"
    assert p.slot_for_title("School Dinner - Meatballs / Pasta") is None


def test_kiev():
    r = p.parse_description(KIEV)
    assert r["headline"].startswith("Quick - oven")
    assert p.badge_for(r["headline"]) == "Quick"
    assert [i["text"] for i in r["ingredients"]] == ["4 garlic chicken Kievs", "~1kg Maris Piper potatoes", "Peas"]
    assert len(r["method"]) == 2, r["method"]
    assert r["extras"][0]["label"] == "Tonight"
    assert p.prep_lines_for(r, tomorrow=False) == [
        "Make the Shepherd's Pie for tomorrow (see Tuesday) - make it big, it's Wednesday's lunch too."]


def test_shepherds():
    r = p.parse_description(SHEP)
    assert p.badge_for(r["headline"]) == "Make ahead"
    assert r["intro"] == ["Makes enough for dinner + 2 lunches Wednesday."]
    assert r["method"][-1].endswith("Fridge."), r["method"]
    assert r["extras"] == [{"label": "Reheat", "text": "190°C / 170 fan for 35-40 mins till bubbling."}]


def test_split():
    r = p.parse_description(SPLIT)
    assert r["headline"] is None
    s = p.lunch_split("Soup & Baguette / Chicken Wrap", r["extras"])
    assert [(x["who"], x["office"], x["title"]) for x in s] == [("Emma", False, "Soup & Baguette"), ("Geraint", True, "Chicken Wrap")]
    assert p.prep_lines_for(r, tomorrow=True) == ["Geraint: pack a wrap the night before (office day)"]


def test_prep_sections():
    r = p.parse_description(PREP)
    assert p.minutes_from(r["headline"]) == 45
    heads = [i["text"] for i in r["ingredients"] if i["header"]]
    assert heads == ["Greek chicken", "Red pepper & tomato soup"]
    assert r["method"][0].startswith("Greek chicken: Toss")
    assert any(m.startswith("Red pepper & tomato soup: Soften") for m in r["method"]), r["method"]


def test_leftovers():
    r = p.parse_description(LEFT)
    assert p.minutes_from(r["headline"]) == 3
    assert r["ingredients"] == []
    # No ingredient list: the paragraph is the method, not an intro.
    assert r["intro"] and not r["method"]
    assert p.badge_for(r["headline"], "Shepherd's Pie Leftovers") == "Leftovers"
    assert p.badge_for("Sunday roast") == "Roast"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
