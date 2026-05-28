# LU2CO V1 — Project Notes

## Testimonials Section — Column Structure

The testimonials grid has 6 columns. Their classes must always be exactly:

| Col | Class |
|-----|-------|
| 0   | `t-col t-col--extra` (absolute, fills the top-left gap in the tilted perspective) |
| 1   | `t-col` |
| 2   | `t-col t-col--reverse` |
| 3   | `t-col` |
| 4   | `t-col t-col--reverse` |
| 5   | `t-col` |

**Do not remove `t-col--reverse` from cols 2 and 4.** Removing it makes all columns scroll in the same direction, breaking the fill effect and causing columns to visually disappear.

**Image count is not a concern** — more images will be added over time. Only the structure matters.

Each column has 3 `t-repeat` blocks (duplicates for seamless infinite scroll). When adding new images, update all 3 repeats in each column with the same image list.
