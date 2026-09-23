#!/usr/bin/env python3
"""Generate verified 2D maps for common image blend modes.

Coordinates and values are normalized to [0, 1]:
    x = B (backdrop / bottom layer)
    y = S (source / top layer)
    color = R (result)

The definitions follow the separable blend functions used by PDF/W3C,
including the piecewise Soft Light function.  Photoshop-style additions
(Linear Burn/Dodge, Vivid/Linear/Pin Light, Hard Mix) are explicitly clamped.
"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "figures"
DOCS_DIR = REPO_ROOT / "docs"
N = 1001


def clamp(x: np.ndarray) -> np.ndarray:
    return np.clip(x, 0.0, 1.0)


def darken(B, S):
    return np.minimum(B, S)


def multiply(B, S):
    return B * S


def color_burn(B, S):
    # Canonical boundary: S=0 -> 0. Otherwise max(0, 1-(1-B)/S).
    with np.errstate(divide="ignore", invalid="ignore"):
        raw = 1.0 - (1.0 - B) / S
    return np.where(S <= 0.0, 0.0, np.maximum(0.0, raw))


def linear_burn(B, S):
    return clamp(B + S - 1.0)


def darker_color(B, S):
    # For scalar grayscale, whole-pixel Darker Color reduces to min(B,S).
    return np.minimum(B, S)


def lighten(B, S):
    return np.maximum(B, S)


def screen(B, S):
    return 1.0 - (1.0 - B) * (1.0 - S)


def color_dodge(B, S):
    # Canonical boundary: S=1 -> 1. Otherwise min(1, B/(1-S)).
    with np.errstate(divide="ignore", invalid="ignore"):
        raw = B / (1.0 - S)
    return np.where(S >= 1.0, 1.0, np.minimum(1.0, raw))


def linear_dodge(B, S):
    return clamp(B + S)


def lighter_color(B, S):
    # For scalar grayscale, whole-pixel Lighter Color reduces to max(B,S).
    return np.maximum(B, S)


def overlay(B, S):
    # The branch is selected by the backdrop B.
    return np.where(B <= 0.5, 2.0 * B * S, 1.0 - 2.0 * (1.0 - B) * (1.0 - S))


def soft_light(B, S):
    # PDF/W3C definition. The upper branch uses D(B), including its B<=1/4 split.
    D = np.where(B <= 0.25, ((16.0 * B - 12.0) * B + 4.0) * B, np.sqrt(B))
    return np.where(
        S <= 0.5,
        B - (1.0 - 2.0 * S) * B * (1.0 - B),
        B + (2.0 * S - 1.0) * (D - B),
    )


def hard_light(B, S):
    # Overlay with B and S exchanged; the branch is selected by source S.
    return np.where(S <= 0.5, 2.0 * B * S, 1.0 - 2.0 * (1.0 - B) * (1.0 - S))


def vivid_light(B, S):
    # S<1/2: Color Burn with blend 2S. S>=1/2: Color Dodge with blend 2S-1.
    low_blend = 2.0 * S
    high_blend = 2.0 * S - 1.0
    with np.errstate(divide="ignore", invalid="ignore"):
        low_raw = 1.0 - (1.0 - B) / low_blend
        high_raw = B / (1.0 - high_blend)
    low = np.where(low_blend <= 0.0, 0.0, np.maximum(0.0, low_raw))
    high = np.where(high_blend >= 1.0, 1.0, np.minimum(1.0, high_raw))
    return np.where(S < 0.5, low, high)


def linear_light(B, S):
    return clamp(B + 2.0 * S - 1.0)


def pin_light(B, S):
    return np.where(S < 0.5, np.minimum(B, 2.0 * S), np.maximum(B, 2.0 * S - 1.0))


def hard_mix(B, S):
    # Photoshop convention: Vivid Light below 0.5 -> 0; otherwise -> 1.
    return (vivid_light(B, S) >= 0.5).astype(float)


MODES = OrderedDict([
    ("Darken", darken),
    ("Multiply", multiply),
    ("Color Burn", color_burn),
    ("Linear Burn", linear_burn),
    ("Darker Color (grayscale)", darker_color),
    ("Lighten", lighten),
    ("Screen", screen),
    ("Color Dodge", color_dodge),
    ("Linear Dodge (Add)", linear_dodge),
    ("Lighter Color (grayscale)", lighter_color),
    ("Overlay", overlay),
    ("Soft Light", soft_light),
    ("Hard Light", hard_light),
    ("Vivid Light", vivid_light),
    ("Linear Light", linear_light),
    ("Pin Light", pin_light),
    ("Hard Mix", hard_mix),
])


FORMULAS = OrderedDict([
    ("Darken", "min(B, S)"),
    ("Multiply", "B*S"),
    ("Color Burn", "S=0: 0; else max(0, 1-(1-B)/S)"),
    ("Linear Burn", "clamp(B+S-1)"),
    ("Darker Color (grayscale)", "min(B, S); RGB version compares whole-pixel luminosity"),
    ("Lighten", "max(B, S)"),
    ("Screen", "1-(1-B)(1-S)"),
    ("Color Dodge", "S=1: 1; else min(1, B/(1-S))"),
    ("Linear Dodge (Add)", "clamp(B+S)"),
    ("Lighter Color (grayscale)", "max(B, S); RGB version compares whole-pixel luminosity"),
    ("Overlay", "B<=.5: 2BS; else 1-2(1-B)(1-S)"),
    ("Soft Light", "S<=.5: B-(1-2S)B(1-B); else B+(2S-1)(D(B)-B)"),
    ("Hard Light", "S<=.5: 2BS; else 1-2(1-B)(1-S)"),
    ("Vivid Light", "S<.5: Burn(B,2S); else Dodge(B,2S-1)"),
    ("Linear Light", "clamp(B+2S-1)"),
    ("Pin Light", "S<.5: min(B,2S); else max(B,2S-1)"),
    ("Hard Mix", "VividLight(B,S)<.5: 0; else 1"),
])


def scalar(f, b, s):
    return float(np.asarray(f(np.array(b, dtype=float), np.array(s, dtype=float))))


def verify() -> list[str]:
    eps = 1e-12
    checks = [
        ("Overlay lower", scalar(overlay, .25, .8), .4),
        ("Overlay upper", scalar(overlay, .75, .2), .6),
        ("Overlay seam", scalar(overlay, .5, .73), .73),
        ("Hard Light lower", scalar(hard_light, .8, .25), .4),
        ("Hard Light upper", scalar(hard_light, .2, .75), .6),
        ("Hard Light seam", scalar(hard_light, .73, .5), .73),
        ("Soft Light neutral", scalar(soft_light, .37, .5), .37),
        ("Soft Light black source", scalar(soft_light, .37, 0), .37**2),
        ("Soft Light D polynomial", scalar(soft_light, .25, 1), .5),
        ("Soft Light D sqrt", scalar(soft_light, .36, 1), .6),
        ("Color Burn S=0", scalar(color_burn, .8, 0), 0),
        ("Color Burn clamp", scalar(color_burn, .2, .5), 0),
        ("Color Dodge S=1", scalar(color_dodge, .2, 1), 1),
        ("Color Dodge clamp", scalar(color_dodge, .8, .5), 1),
        ("Vivid Light neutral", scalar(vivid_light, .37, .5), .37),
        ("Vivid Light S=0", scalar(vivid_light, .8, 0), 0),
        ("Vivid Light S=1", scalar(vivid_light, .2, 1), 1),
        ("Pin Light low", scalar(pin_light, .8, .2), .4),
        ("Pin Light high", scalar(pin_light, .2, .8), .6),
        ("Pin Light neutral", scalar(pin_light, .37, .5), .37),
        ("Hard Mix low", scalar(hard_mix, .2, .5), 0),
        ("Hard Mix threshold", scalar(hard_mix, .5, .5), 1),
    ]
    lines = []
    for name, actual, expected in checks:
        assert abs(actual - expected) <= eps, (name, actual, expected)
        lines.append(f"PASS  {name}: {actual:.12g}")
    return lines


def draw_panel(ax, R, title, show_labels=True):
    im = ax.imshow(R, origin="lower", extent=(0, 1, 0, 1), vmin=0, vmax=1,
                   cmap="viridis", interpolation="nearest", aspect="equal")
    ax.contour(np.linspace(0, 1, R.shape[1]), np.linspace(0, 1, R.shape[0]), R,
               levels=[.25, .5, .75], colors="white", linewidths=.45, alpha=.65)
    ax.set_title(title, fontsize=10, pad=5)
    ax.set_xticks([0, .25, .5, .75, 1])
    ax.set_yticks([0, .25, .5, .75, 1])
    ax.tick_params(labelsize=7)
    if show_labels:
        ax.set_xlabel("B  (backdrop / bottom)", fontsize=8)
        ax.set_ylabel("S  (source / top)", fontsize=8)
    return im


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    report = verify()
    values = np.linspace(0.0, 1.0, N)
    B, S = np.meshgrid(values, values)
    results = OrderedDict((name, clamp(fn(B, S))) for name, fn in MODES.items())

    # Global range and finite-value verification on the complete sampled grid.
    for name, R in results.items():
        assert np.isfinite(R).all(), f"{name}: non-finite value"
        assert R.min() >= 0.0 and R.max() <= 1.0, f"{name}: out of range"
        report.append(f"PASS  {name}: grid finite, range [{R.min():.6g}, {R.max():.6g}]")

    fig, axes = plt.subplots(5, 4, figsize=(15, 18), constrained_layout=True)
    axes = axes.ravel()
    for ax, (name, R) in zip(axes, results.items()):
        im = draw_panel(ax, R, name)
    for ax in axes[len(results):]:
        ax.axis("off")
    cbar = fig.colorbar(im, ax=list(axes), location="right", shrink=.92, pad=.02)
    cbar.set_label("R  (result)", fontsize=11)
    fig.suptitle("Blend mode functions — x: B, y: S, color: R", fontsize=17)
    fig.savefig(OUT_DIR / "blend_modes_overview.png", dpi=300, facecolor="white")
    plt.close(fig)

    singles = OUT_DIR / "single_modes"
    singles.mkdir(exist_ok=True)
    for name, R in results.items():
        fig, ax = plt.subplots(figsize=(7.2, 6.2), constrained_layout=True)
        im = draw_panel(ax, R, name)
        cbar = fig.colorbar(im, ax=ax)
        cbar.set_label("R  (result)")
        safe = name.lower().replace(" ", "_").replace("(", "").replace(")", "")
        fig.savefig(singles / f"{safe}.png", dpi=300, facecolor="white")
        plt.close(fig)

    with (DOCS_DIR / "FORMULAS_AND_CHECKS.txt").open("w", encoding="utf-8") as f:
        f.write("Definitions (B,S,R normalized to [0,1])\n")
        f.write("=========================================\n")
        for name, formula in FORMULAS.items():
            f.write(f"{name}: {formula}\n")
        f.write("\nNotes\n=====\n")
        f.write("D(B)=((16B-12)B+4)B for B<=0.25; otherwise sqrt(B).\n")
        f.write("Darker/Lighter Color select an entire RGB pixel; their grayscale maps equal Darken/Lighten.\n")
        f.write("All arithmetic modes shown here are clamped to [0,1].\n\n")
        f.write("Automated checks\n================\n")
        f.write("\n".join(report) + "\n")
    print(f"Generated {len(results)} modes in: {OUT_DIR}")
    print("All verification checks passed.")


if __name__ == "__main__":
    main()
