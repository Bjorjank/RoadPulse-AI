"""Handle approximate container frame counts without hiding large decode gaps."""


def decode_warning(processed, reported):
    if processed <= 0:
        raise ValueError("Video contains no readable frames")
    missing = reported - processed
    if missing <= 0:
        return None
    # Permit only a tiny tail discrepancy. This is not proof of a clean EOF.
    if missing > 3 or missing / max(reported, 1) > 0.01:
        raise ValueError(f"Video decode ended early: {processed}/{reported} frames")
    return (
        f"Partial analysis warning: decoded {processed}/{reported} reported frames. "
        f"The final {missing} reported frame(s) were unavailable; metadata may be inaccurate "
        "or the video tail may be damaged. Counts and exports cover decoded frames only."
    )
