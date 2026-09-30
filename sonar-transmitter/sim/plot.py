"""Shared plot styling so every Sim-0 figure reads the same way."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from sim0 import BAND  # noqa: E402

# fixed categorical order (validated palette): blue, orange, aqua, yellow, magenta, green, violet, red
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#898781", "#e4e3df"

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "#fcfcfb", "savefig.facecolor": "white",
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": INK2, "ytick.color": INK2, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
    "lines.linewidth": 1.2, "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold",
    "legend.frameon": False, "legend.fontsize": 9, "figure.dpi": 110, "savefig.dpi": 140,
})


def band(ax, unit=1e3, label=True):
    """Shade the 100-500 kHz operating band. `unit` = Hz per x-axis unit."""
    ax.axvspan(BAND[0] / unit, BAND[1] / unit, color="#86b6ef", alpha=0.18, lw=0,
               label="100–500 kHz band" if label else None)


def save(fig, path):
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print("  wrote", path)


def legend_below(ax, ncol=2):
    """Legend under the axes, for panels whose traces fill the whole plot area."""
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=ncol, fontsize=8)
