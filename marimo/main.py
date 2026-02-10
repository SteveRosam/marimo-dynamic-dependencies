# /// script
# [tool.marimo.display]
# theme = "dark"
# ///

import marimo

__generated_with = "0.19.9"
app = marimo.App(width="full")


@app.cell
def _():
    import os
    import marimo as mo
    import numpy as np
    import plotly.express as px

    return mo, np, px


@app.cell
def _(mo, np, px):
    # Generate sine wave data
    x = np.linspace(0, 4 * np.pi, 200)
    y = np.sin(x)

    # Create the plot
    fig = px.line(x=x, y=y, title="Sine Wave", labels={"x": "x", "y": "sin(x)"})
    fig.update_layout(template="plotly_dark")

    mo.md("## Sine Wave Demo")
    mo.ui.plotly(fig)
    return


@app.cell
def _():
    #jibber Jabber
    return


if __name__ == "__main__":
    app.run()
