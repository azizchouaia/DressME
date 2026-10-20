"""Illustrated Tunisian garments (SVG). Rendered to transparent PNG by render.py."""
import json

DEFS = """<defs>
<filter id="soft" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation="0.6"/></filter>
<linearGradient id="shade" x1="0" x2="1"><stop offset="0" stop-color="#000" stop-opacity=".10"/>
<stop offset=".35" stop-color="#000" stop-opacity="0"/><stop offset=".7" stop-color="#fff" stop-opacity=".10"/>
<stop offset="1" stop-color="#000" stop-opacity=".12"/></linearGradient>
<pattern id="gold" width="16" height="16" patternUnits="userSpaceOnUse"><rect width="16" height="16" fill="#b8862b"/>
<path d="M8 1 L15 8 L8 15 L1 8Z" fill="#e7c46a"/><circle cx="8" cy="8" r="2" fill="#7a4b12"/></pattern>
<pattern id="goldred" width="14" height="14" patternUnits="userSpaceOnUse"><rect width="14" height="14" fill="#d9a93f"/>
<path d="M7 1 L13 7 L7 13 L1 7Z" fill="#8f1d24"/></pattern>
<pattern id="kstripe" width="44" height="10" patternUnits="userSpaceOnUse"><rect width="44" height="10" fill="#e8dcc4"/>
<rect width="18" height="10" fill="#6b4a2f"/><rect x="22" width="4" height="10" fill="#6b4a2f"/></pattern>
<pattern id="weave" width="14" height="14" patternUnits="userSpaceOnUse"><rect width="14" height="14" fill="#d9b779"/>
<path d="M0 3.5h14M0 10.5h14" stroke="#b8924f" stroke-width="3"/><path d="M3.5 0v7M10.5 7v7" stroke="#e8cf9c" stroke-width="3"/></pattern>
<pattern id="fouta" width="60" height="10" patternUnits="userSpaceOnUse"><rect width="60" height="10" fill="#f4f1ea"/>
<rect width="14" height="10" fill="#2c5d9e"/><rect x="18" width="3" height="10" fill="#c23a2c"/><rect x="25" width="6" height="10" fill="#2c5d9e"/>
<rect x="35" width="3" height="10" fill="#2c5d9e"/></pattern>
<pattern id="silk" width="8" height="8" patternUnits="userSpaceOnUse"><rect width="8" height="8" fill="#f5f2ea"/>
<rect width="1.2" height="8" fill="#e2dccd"/></pattern>
</defs>"""

def svg(body, w=400, h=520):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">{DEFS}{body}</svg>'

S = 'stroke="#00000033" stroke-width="2" stroke-linejoin="round"'

def jebba(base, band, label_band="url(#gold)"):
    body = "M150,40 Q200,72 250,40 L302,58 L340,150 L300,168 L296,478 Q200,494 104,478 L100,168 L60,150 L98,58 Z"
    return svg(f"""
<path d="{body}" fill="{base}" {S}/>
<path d="{body}" fill="url(#shade)"/>
<path d="M150,40 Q200,72 250,40 Q236,62 200,80 Q164,62 150,40Z" fill="#00000022"/>
<path d="M188,78 L212,78 L210,260 L190,260 Z" fill="{label_band}" {S}/>
<path d="M104,452 Q200,468 296,452 L296,478 Q200,494 104,478Z" fill="{label_band}"/>
<path d="M60,150 L100,168 L104,150 L68,134Z" fill="{label_band}"/><path d="M340,150 L300,168 L296,150 L332,134Z" fill="{label_band}"/>
<path d="M200,262 v190" stroke="#00000014" stroke-width="2"/>""")

def kachabia():
    body = ("M200,28 Q240,40 250,96 L330,120 L372,470 Q300,492 200,492 Q100,492 28,470 L70,120 L150,96 Q160,40 200,28Z")
    return svg(f"""
<path d="{body}" fill="url(#kstripe)" {S}/>
<path d="{body}" fill="url(#shade)"/>
<path d="M200,28 Q240,40 250,96 Q228,128 200,132 Q172,128 150,96 Q160,40 200,28Z" fill="#5a3d26" {S}/>
<path d="M200,40 Q226,52 232,94 Q214,114 200,116 Q186,114 168,94 Q174,52 200,40Z" fill="#2a1d12" opacity=".55"/>
<path d="M200,132 L200,490" stroke="#3b2817" stroke-width="3"/>
<path d="M200,16 l0,14" stroke="#3b2817" stroke-width="3"/><circle cx="200" cy="14" r="7" fill="#3b2817"/>
<path d="M28,470 Q100,492 200,492 Q300,492 372,470" fill="none" stroke="#3b2817" stroke-width="6" stroke-dasharray="3 5"/>""")

def sefsari():
    return svg(f"""
<path d="M120,30 Q200,8 280,30 Q330,140 350,300 Q362,420 330,490 Q260,505 200,500 Q140,505 70,490 Q38,420 50,300 Q70,140 120,30Z" fill="url(#silk)" {S}/>
<path d="M120,30 Q200,8 280,30 Q330,140 350,300 Q362,420 330,490 Q260,505 200,500 Q140,505 70,490 Q38,420 50,300 Q70,140 120,30Z" fill="url(#shade)"/>
<path d="M150,40 Q130,200 118,490 M200,30 Q196,250 200,498 M250,40 Q272,220 284,494" stroke="#00000018" stroke-width="5" fill="none"/>
<path d="M120,30 Q200,8 280,30 Q250,60 200,62 Q150,60 120,30Z" fill="#e6e0d2"/>
<path d="M70,490 Q140,505 200,500 Q260,505 330,490" fill="none" stroke="#c9a457" stroke-width="5"/>""")

def blouza():
    return svg(f"""
<path d="M160,40 Q200,64 240,40 L262,52 L268,190 Q330,330 356,486 Q200,506 44,486 Q70,330 132,190 L138,52Z" fill="#9d1f2b" {S}/>
<path d="M160,40 Q200,64 240,40 L262,52 L268,190 Q330,330 356,486 Q200,506 44,486 Q70,330 132,190 L138,52Z" fill="url(#shade)"/>
<path d="M150,60 Q200,88 250,60 L264,190 Q200,210 136,190Z" fill="url(#goldred)" {S}/>
<path d="M132,190 Q200,212 268,190 L272,206 Q200,228 128,206Z" fill="#e3b955"/>
<path d="M60,452 Q200,474 340,452 L348,476 Q200,498 52,476Z" fill="url(#goldred)"/>
<path d="M160,40 Q200,64 240,40 Q222,58 200,66 Q178,58 160,40Z" fill="#00000030"/>""")

def chechia():
    return svg(f"""
<ellipse cx="200" cy="420" rx="150" ry="34" fill="#7d1418"/>
<path d="M50,420 Q56,230 90,170 L310,170 Q344,230 350,420 Q200,456 50,420Z" fill="#b5222a" {S}/>
<path d="M50,420 Q56,230 90,170 L310,170 Q344,230 350,420 Q200,456 50,420Z" fill="url(#shade)"/>
<ellipse cx="200" cy="170" rx="110" ry="28" fill="#c9343b" {S}/>
<circle cx="200" cy="168" r="8" fill="#1d1b1e"/>
<path d="M200,168 Q250,180 268,240 Q276,290 262,330" stroke="#1d1b1e" stroke-width="5" fill="none"/>
<path d="M262,330 l-16,80 M262,330 l-4,84 M262,330 l8,82 M262,330 l20,76 M262,330 l-26,72" stroke="#1d1b1e" stroke-width="4"/>""", 400, 480)

def balgha(color, edge, stitch):
    one = (f'<path d="M0,-150 Q44,-110 50,-10 Q54,80 40,140 Q0,160 -40,140 Q-54,80 -50,-10 Q-44,-110 0,-150Z" fill="{color}" {S}/>'
           f'<path d="M0,-150 Q44,-110 50,-10 Q54,80 40,140 Q0,160 -40,140 Q-54,80 -50,-10 Q-44,-110 0,-150Z" fill="url(#shade)"/>'
           f'<path d="M-38,10 Q0,-6 38,10 L42,130 Q0,148 -42,130Z" fill="{edge}" opacity=".9"/>'
           f'<path d="M0,-130 Q30,-100 36,-20 Q0,-30 -36,-20 Q-30,-100 0,-130Z" fill="none" stroke="{stitch}" stroke-width="3" stroke-dasharray="4 4"/>')
    return svg(f'<g transform="translate(140,250) rotate(-8)">{one}</g><g transform="translate(262,262) rotate(6)">{one}</g>', 400, 460)

def fouta():
    return svg(f"""
<path d="M70,40 L330,40 L338,420 L62,420Z" fill="url(#fouta)" {S}/>
<path d="M70,40 L330,40 L338,420 L62,420Z" fill="url(#shade)"/>
<path d="M70,40 L330,40 L332,70 L68,70Z" fill="#00000014"/>
{''.join(f'<path d="M{66+i*9},420 l{(i%3)-1},44" stroke="#2c5d9e" stroke-width="3"/>' for i in range(31))}""", 400, 480)

def serwal():
    return svg(f"""
<path d="M110,40 L290,40 L300,70 Q360,260 330,440 L344,476 L256,480 L250,446 Q220,300 200,250 Q180,300 150,446 L144,480 L56,476 L70,440 Q40,260 100,70Z" fill="#efe9dc" {S}/>
<path d="M110,40 L290,40 L300,70 Q360,260 330,440 L344,476 L256,480 L250,446 Q220,300 200,250 Q180,300 150,446 L144,480 L56,476 L70,440 Q40,260 100,70Z" fill="url(#shade)"/>
<path d="M100,70 L300,70 L290,40 L110,40Z" fill="#d8cfbb"/>
<path d="M120,56 h160" stroke="#a3896a" stroke-width="3" stroke-dasharray="6 6"/>
<path d="M70,440 L150,446 M250,446 L330,440" stroke="#c9bfa8" stroke-width="10"/>
<path d="M140,120 Q120,260 110,420 M260,120 Q280,260 290,420" stroke="#00000014" stroke-width="5" fill="none"/>""", 400, 500)

def koffa():
    return svg(f"""
<path d="M120,150 Q130,40 200,40 Q270,40 280,150" fill="none" stroke="#7a4b23" stroke-width="16" stroke-linecap="round"/>
<path d="M70,150 L330,150 L300,440 Q200,456 100,440Z" fill="url(#weave)" {S}/>
<path d="M70,150 L330,150 L300,440 Q200,456 100,440Z" fill="url(#shade)"/>
<path d="M70,150 L330,150 L327,176 L73,176Z" fill="#8b5a2b"/>
<circle cx="140" cy="250" r="16" fill="#c23a2c"/><circle cx="200" cy="262" r="16" fill="#2c5d9e"/><circle cx="260" cy="250" r="16" fill="#e2a72e"/>
<path d="M120,320 h160" stroke="#c23a2c" stroke-width="6"/><path d="M116,350 h168" stroke="#2c5d9e" stroke-width="6"/>""", 400, 480)

def linen_shirt():
    body = "M150,40 L250,40 L320,70 L372,200 L326,220 L300,160 L300,470 Q200,484 100,470 L100,160 L74,220 L28,200 L80,70Z"
    return svg(f"""
<path d="{body}" fill="#e9dcc2" {S}/><path d="{body}" fill="url(#shade)"/>
<path d="M150,40 L200,90 L250,40 L236,30 L200,62 L164,30Z" fill="#dccdb0" {S}/>
<path d="M192,90 L208,90 L208,470 L192,470Z" fill="#d6c6a6"/>
<path d="M176,96 l24,0 M176,120 l24,0 M176,144 l24,0" stroke="#2c5d9e" stroke-width="3"/>
{''.join(f'<circle cx="200" cy="{110+i*60}" r="4" fill="#8a6b45"/>' for i in range(6))}
<path d="M164,92 Q172,150 176,200 M236,92 Q228,150 224,200" stroke="#2c5d9e" stroke-width="3" stroke-dasharray="5 4" fill="none"/>""")

ITEMS = [
 ("tn_jebba_white","traditional","white embroidered jebba","Medina artisans","Men's sleeveless Tunisian robe in cream cotton, gold silk embroidery on the chest (sfifa).", jebba("#f3efe5","#b8862b")),
 ("tn_jebba_grey","traditional","grey wool jebba","Kairouan weavers","Winter jebba in light grey wool with a red-gold embroidered placket.", jebba("#a7a3a0","#b8862b","url(#goldred)")),
 ("tn_kachabia","traditional","striped hooded kachabia","Kairouan weavers","Hooded wool cloak with brown and cream stripes, worn over clothes in winter.", kachabia()),
 ("tn_sefsari","traditional","white silk sefsari","Medina artisans","Traditional women's wrap in fine striped white silk with a golden border.", sefsari()),
 ("tn_blouza","dress","embroidered red blouza","Mahdia ateliers","Festive dress in red velvet, gold embroidered bodice and hem (Mahdia style).", blouza()),
 ("tn_chechia","accessory","red chechia","Souk Chaouachia","Red felted wool cap with a black silk tassel, hand made in the souk of Tunis.", chechia()),
 ("tn_balgha_yellow","shoes","yellow balgha","Medina artisans","Backless pointed leather slippers in saffron yellow.", balgha("#e3b13a","#c48f22","#8a5a10")),
 ("tn_balgha_red","shoes","red embroidered balgha","Medina artisans","Red leather balgha with gold stitching, for weddings and Eid.", balgha("#b3262d","#8d1a20","#e7c46a")),
 ("tn_fouta","accessory","striped fouta","Nabeul weavers","Hand-woven cotton fouta with blue, white and red stripes and fringes; worn as a scarf or beach wrap.", fouta()),
 ("tn_serwal","bottom","white serwal","Medina artisans","Loose traditional trousers in cream cotton, worn with the jebba.", serwal()),
 ("tn_koffa","accessory","alfa koffa basket bag","Nabeul weavers","Woven alfa-grass basket bag with leather handles and wool pompoms.", koffa()),
 ("tn_linen_shirt","top","embroidered linen shirt","Sidi Linen Co.","Modern linen shirt with blue Tunisian embroidery along the collar.", linen_shirt()),
]
meta = []
for iid, cat, name, brand, desc, s in ITEMS:
    open(f"{iid}.svg","w").write(s)
    meta.append({"item_id": iid, "category": cat, "subcategory": name, "local_tag": brand, "description": desc})
json.dump(meta, open("meta.json","w"), indent=1)
print(len(meta))
