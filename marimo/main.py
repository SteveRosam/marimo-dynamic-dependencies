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

    return (mo,)


@app.cell
def _(mo):
    import cowsay

    message = cowsay.get_output_string("cow", "Installed at runtime!")
    mo.md(f"```\n{message}\n```")
    return


@app.cell
def _():
    #jksdfh jksdfhj sdhjk f
    # asdasdasd aaaa
    return


if __name__ == "__main__":
    app.run()
