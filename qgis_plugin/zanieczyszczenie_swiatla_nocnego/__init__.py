# -*- coding: utf-8 -*-
def classFactory(iface):
    from .plugin import NightLightPlugin
    return NightLightPlugin(iface)
