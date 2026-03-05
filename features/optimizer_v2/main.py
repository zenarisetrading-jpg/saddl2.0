import streamlit as st

def render_optimizer_v2():
    """
    Render the premium optimizer shell (V2.0 UX) backed by V2.1 logic.
    """
    from features.optimizer_shared import OptimizerModule
    OptimizerModule().run()
