"""Resolve a hemisphere-free region choice to a catalog entry."""


def region_options(rois, hemisphere, only_fdr=False):
    """Filter by saved mask availability and display only abbreviated ROI names."""
    side = {"Left": "L", "Right": "R"}[hemisphere]
    options = {}
    for entry in rois.values():
        if entry["hemisphere"] == side:
            passing = entry["hemisphere_counts"]
            left = passing["lh"]["passing"] > 0
            right = passing["rh"]["passing"] > 0
            if only_fdr and not (left or right):
                continue
            options[entry["label"]] = entry["label"]
    return dict(sorted(options.items(), key=lambda item: item[0].casefold()))


def resolve_roi(rois, hemisphere, region):
    if region is None:
        return None
    side = {"Left": "L", "Right": "R"}[hemisphere]
    key = f"{side}_{region}"
    entry = rois.get(key)
    if entry is None or entry["hemisphere"] != side:
        return None
    return key
