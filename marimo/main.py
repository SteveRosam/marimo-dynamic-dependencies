# /// script
# [tool.marimo.display]
# theme = "dark"
# ///

import marimo

__generated_with = "0.19.11"
app = marimo.App(width="full")


@app.cell
def _():
    import os
    import marimo as mo
    import numpy as np
    import plotly.express as px
    import quixlake

    return (mo,)


@app.cell
def _(mo):
    import cowsay

    message = cowsay.get_output_string("cow", "MOO!")
    mo.md(f"```\n{message}\n```")
    return


@app.cell
def _():
    #jksdfh jksdfhj sdhjk f
    # asdasdasd aaaa gfh fgh fg
    return


if __name__ == "__main__":
    app.run()
