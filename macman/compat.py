"""Narrow frontend fixes for pinned ipyniivue 2.4.4 in marimo.

Nested anywidget models provide set/save_changes, not onChange. Also the
upstream layer-list handler neither awaits parsing nor removes old layers.
The scalar parser also treats an explicit zero minimum as absent, which makes
the automatic minimum NaN for maps with missing vertices.
Keep fixes checked against exact snippets so an upstream upgrade fails loudly.
This adapts the bundled widget; it does not replace NiiVue rendering.
"""

from ipyniivue import NiiVue

from .layer_updates import LAYER_UPDATE_HANDLER


def patched_esm():
    source = str(NiiVue._esm)
    replacements = {
        # NaN scalars must leave the base surface untouched. Otherwise NaN LUT
        # indices become undefined colors and Uint8 conversion paints black.
        "let l=D*C.values[y+r];if(l<n)continue;": "let l=D*C.values[y+r];if(!Number.isFinite(l)||l<n)continue;",
        "e.cal_min=i||0,i||(e.cal_min=h),e.cal_max=o||0,o||(e.cal_max=c)": "e.cal_min=i??h,e.cal_max=o??c",
        "A.onChange(I)": '(typeof A.onChange==="function"?A.onChange(I):(A.set(I),A.save_changes()))',
        "A.onChange(c)": '(typeof A.onChange==="function"?A.onChange(c):(A.set(c),A.save_changes()))',
        "function R(){r2(I,A,B),A.updateMesh(B.gl),B.updateGLVolume()}": (
            LAYER_UPDATE_HANDLER
        ),
        # Own the initial listeners as well as listeners created by replacements.
        "function h0(A,I,B){": "function h0(A,I,B,initialLayerDisposers){",
        "let o=h0(B,I,A);": "let o=h0(B,I,A,i);",
        'I.off("change:layers",R),I.off("msg:custom",d)': (
            'I.off("change:layers",R),I.off("msg:custom",d),disposeLayers()'
        ),
        # A later layer can fail after earlier layers installed listeners.
        'async function r2(A,I,B){let C=[],g=A.get("layers");': (
            'async function r2(A,I,B){let C=[],g=A.get("layers");try{'
        ),
        "else I.layers=[];return C}function h0": (
            "else I.layers=[];return C}catch(error){"
            "for(const dispose of C)dispose();throw error}}function h0"
        ),
    }
    for old, new in replacements.items():
        if source.count(old) != 1:
            raise RuntimeError(
                "ipyniivue frontend changed; review macman.compat before upgrading"
            )
        source = source.replace(old, new)
    return source


class MarimoNiiVue(NiiVue):
    _esm = patched_esm()


class HumanNiiVue(MarimoNiiVue):
    # Distinct module contents give each figure its own module-level NiiVue
    # singleton, event handlers and disposal state in anywidget's module cache.
    _esm = str(MarimoNiiVue._esm) + "\n// MACMAN human viewer module\n"


class LeftResultNiiVue(MarimoNiiVue):
    _esm = str(MarimoNiiVue._esm) + "\n// MACMAN left NHP viewer module\n"


class RightResultNiiVue(MarimoNiiVue):
    _esm = str(MarimoNiiVue._esm) + "\n// MACMAN right NHP viewer module\n"
