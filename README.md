# Blend Mode Function Atlas

Let $B,S,R\in[0,1]$ denote backdrop, source, and result. Let

$$C(x)=\min(1,\max(0,x)).$$

## Darken

| Mode | Formula |
|---|---|
| Darken | $R=\min(B,S)$ |
| Multiply | $R=BS$ |
| Color Burn | $R=0$ if $S=0$; otherwise $R=\max\left(0,1-\frac{1-B}{S}\right)$ |
| Linear Burn | $R=C(B+S-1)$ |
| Darker Color (grayscale) | $R=\min(B,S)$ |

## Lighten

| Mode | Formula |
|---|---|
| Lighten | $R=\max(B,S)$ |
| Screen | $R=1-(1-B)(1-S)$ |
| Color Dodge | $R=1$ if $S=1$; otherwise $R=\min\left(1,\frac{B}{1-S}\right)$ |
| Linear Dodge (Add) | $R=C(B+S)$ |
| Lighter Color (grayscale) | $R=\max(B,S)$ |

## Contrast and light

| Mode | Formula |
|---|---|
| Overlay | $R=2BS$ if $B\leq\frac12$; otherwise $R=1-2(1-B)(1-S)$ |
| Soft Light | $R=B-(1-2S)B(1-B)$ if $S\leq\frac12$; otherwise $R=B+(2S-1)(D(B)-B)$ |
| Hard Light | $R=2BS$ if $S\leq\frac12$; otherwise $R=1-2(1-B)(1-S)$ |
| Vivid Light | $R=\operatorname{Burn}(B,2S)$ if $S<\frac12$; otherwise $R=\operatorname{Dodge}(B,2S-1)$ |
| Linear Light | $R=C(B+2S-1)$ |
| Pin Light | $R=\min(B,2S)$ if $S<\frac12$; otherwise $R=\max(B,2S-1)$ |
| Hard Mix | $R=0$ if $\operatorname{VividLight}(B,S)<\frac12$; otherwise $R=1$ |

where

$$
D(B)=
\begin{cases}
((16B-12)B+4)B, & B\leq\frac14,\\
\sqrt{B}, & B>\frac14.
\end{cases}
$$

For RGB images, Darker Color and Lighter Color select a whole pixel by luminosity; the scalar formulas above are their grayscale reductions.

## Reproduce

```bash
python -m pip install -r requirements.txt
python src/generate_blend_mode_maps.py
```

![All blend-mode functions](figures/blend_modes_overview.png)
