"""Master map: every navigation spacecraft as a small tree of its identifiers, on one canvas you can move around."""
from ui.components.master_map import master_map_canvas
from ui.pages_data import load_master_map_data

master_map_canvas(load_master_map_data(), height=760)
