"""Streamlit's AppTest mis-reads a string default on st.segmented_control as a list of characters."""
from streamlit.testing.v1 import element_tree

element_tree.ButtonGroup.indices = property(
    lambda self: [self.options.index(self.format_func(v)) for v in ([self.value] if isinstance(self.value, str) else self.value)])
