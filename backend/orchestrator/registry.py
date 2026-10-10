"""The only place where agents are registered. Adding an agent = one line."""

from agents.localshop.agent import LocalShopAgent
from agents.profile.agent import ProfileAgent
from agents.smartbuy.agent import SmartBuyAgent
from agents.stylist.agent import StylistAgent
from agents.tryon.agent import TryOnAgent
from agents.vision.agent import VisionAgent

AGENTS = {
    a.name: a
    for a in [
        VisionAgent(),
        StylistAgent(),
        ProfileAgent(),
        SmartBuyAgent(),
        LocalShopAgent(),
        TryOnAgent(),
    ]
}


def get_tools():
    from agents.localshop.tool import tool as localshop
    from agents.profile.tool import tool as profile
    from agents.smartbuy.tool import tool as smartbuy
    from agents.stylist.tool import tool as stylist
    from agents.tryon.tool import tool as tryon
    from agents.vision.tool import tool as vision

    return [vision, stylist, profile, smartbuy, localshop, tryon]
