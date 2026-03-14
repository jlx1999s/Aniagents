from typing import Any, Optional

from app.agents.animation_artist import animation_artist_agent
from app.agents.art_director import art_director_agent
from app.agents.character_designer import character_designer_agent
from app.agents.compositor import compositor_agent
from app.agents.director import director_agent
from app.agents.scene_designer import scene_designer_agent
from app.agents.scriptwriter import scriptwriter_agent
from app.agents.sound_director import sound_director_agent
from app.agents.storyboard_artist import storyboard_artist_agent
from app.graph.routing import (
    NODE_ANIMATION_ARTIST,
    NODE_ART_DIRECTOR,
    NODE_CHARACTER_DESIGNER,
    NODE_COMPOSITOR,
    NODE_DIRECTOR,
    NODE_END,
    NODE_SCENE_DESIGNER,
    NODE_SCRIPTWRITER,
    NODE_SOUND_DIRECTOR,
    NODE_STORYBOARD_ARTIST,
    route_from_director,
)
from app.graph.state import ManjuState


def build_graph(checkpointer: Optional[Any] = None):
    try:
        from langgraph.graph import END, StateGraph
    except Exception as exc:
        raise RuntimeError("LangGraph is required to build the graph") from exc

    graph = StateGraph(ManjuState)
    graph.add_node(NODE_DIRECTOR, director_agent)
    graph.add_node(NODE_SCRIPTWRITER, scriptwriter_agent)
    graph.add_node(NODE_ART_DIRECTOR, art_director_agent)
    graph.add_node(NODE_CHARACTER_DESIGNER, character_designer_agent)
    graph.add_node(NODE_SCENE_DESIGNER, scene_designer_agent)
    graph.add_node(NODE_STORYBOARD_ARTIST, storyboard_artist_agent)
    graph.add_node(NODE_ANIMATION_ARTIST, animation_artist_agent)
    graph.add_node(NODE_SOUND_DIRECTOR, sound_director_agent)
    graph.add_node(NODE_COMPOSITOR, compositor_agent)

    graph.set_entry_point(NODE_DIRECTOR)

    graph.add_edge(NODE_SCRIPTWRITER, NODE_ART_DIRECTOR)
    graph.add_edge(NODE_ART_DIRECTOR, NODE_CHARACTER_DESIGNER)
    graph.add_edge(NODE_CHARACTER_DESIGNER, NODE_SCENE_DESIGNER)
    graph.add_edge(NODE_SCENE_DESIGNER, NODE_DIRECTOR)
    graph.add_edge(NODE_STORYBOARD_ARTIST, NODE_DIRECTOR)
    graph.add_edge(NODE_ANIMATION_ARTIST, NODE_SOUND_DIRECTOR)
    graph.add_edge(NODE_SOUND_DIRECTOR, NODE_COMPOSITOR)
    graph.add_edge(NODE_COMPOSITOR, NODE_DIRECTOR)

    graph.add_conditional_edges(
        NODE_DIRECTOR,
        route_from_director,
        {
            NODE_SCRIPTWRITER: NODE_SCRIPTWRITER,
            NODE_ART_DIRECTOR: NODE_ART_DIRECTOR,
            NODE_CHARACTER_DESIGNER: NODE_CHARACTER_DESIGNER,
            NODE_SCENE_DESIGNER: NODE_SCENE_DESIGNER,
            NODE_STORYBOARD_ARTIST: NODE_STORYBOARD_ARTIST,
            NODE_ANIMATION_ARTIST: NODE_ANIMATION_ARTIST,
            NODE_SOUND_DIRECTOR: NODE_SOUND_DIRECTOR,
            NODE_COMPOSITOR: NODE_COMPOSITOR,
            NODE_END: END,
        },
    )

    return graph.compile(checkpointer=checkpointer)
