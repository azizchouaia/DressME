"""Many ways to say the same thing: every one must reach the right agent (no LLM guess)."""

import pytest

from orchestrator.graph import route_by_rules

T = {"wardrobe", "profile", "smartbuy", "localshop", "tryon", "share", "trips", "challenges", "taste", "talk", "stylist"}
CASES={
"gaps":["whats the gap in my closet","what's missing in my wardrobe","what am i missing","what should i buy next","which pieces do i lack","what do i need to buy","gaps in my closet","what is lacking in my wardrobe","qu'est-ce qui manque dans ma garde-robe","chnowa yna9esni","what essentials am i missing","recommend something to buy for my wardrobe","what piece would complete my wardrobe"],
"wardrobe":["show my wardrobe","what clothes do i have","how many pieces do i have","list my clothes","show me my shoes","what jackets do i own","do i have a white shirt","my closet","montre ma garde-robe","what's in my closet","show me all my pieces"],
"stylist":["what should i wear tomorrow","outfit for a wedding","dress me for work","i have an interview tomorrow what do i wear","what to wear on a date","give me a casual look","it's raining what should i wear","suggest an outfit with my jeans","another one","why this outfit","build an outfit around my navy t-shirt","what goes with my black jeans","chnowa nelbes lyoum","je vais à une soirée, quoi porter","outfit for the beach","what should i wear tonight","help me pick an outfit"],
"smartbuy":["should i buy a black jacket for 200 dt","is this blazer worth 300 tnd","i want to buy white sneakers at 150","nechri jupe 60 dinars","is it a good deal a red dress 120dt","should i get a grey hoodie"],
"localshop":["where can i find a white shirt in tunis","find me black boots under 200 dt","any shop selling linen pants in sousse","ou trouver une robe à sfax","buy a blazer near me"],
"challenges":["show me the challenges","any contest this week","what challenges can i join"],
"profile":["what is my style","describe my style","quel est mon style","what kind of style do i have"],
"taste":["i love oversize sweaters","i hate bright colors","i prefer minimal looks","j'adore le beige"],
"tryon":["try it on my avatar","see this outfit on me","show it on my 3d avatar"],
"laundry":["my jeans are dirty","put my white shirt in the laundry","what's in the laundry"],
"trips":["i'm going to paris for 5 days what should i pack","pack for a trip to djerba","valise pour un voyage"],
"share":["share my outfit","post this look"],
}

ROWS = [(want, s) for want, ss in CASES.items() for s in ss]


@pytest.mark.parametrize("want,text", ROWS)
def test_paraphrases(want, text):
    h = route_by_rules(text, T)
    got = "gaps" if h and h.get("gaps") else (h or {}).get("name")
    assert got == ("stylist" if want == "laundry" else want), (text, h)
