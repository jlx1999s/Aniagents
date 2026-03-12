from typing import Dict

from app.graph.state import ManjuState

NODE_DIRECTOR = "Director_Agent"
NODE_SCRIPTWRITER = "Scriptwriter_Agent"
NODE_ART_DIRECTOR = "Art_Director_Agent"
NODE_CHARACTER_DESIGNER = "Character_Designer_Agent"
NODE_STORYBOARD_ARTIST = "Storyboard_Artist_Agent"
NODE_ANIMATION_ARTIST = "Animation_Artist_Agent"
NODE_SOUND_DIRECTOR = "Sound_Director_Agent"
NODE_COMPOSITOR = "Compositor_Agent"
NODE_END = "END"

NODE_SEQUENCE: Dict[str, str] = {
    NODE_SCRIPTWRITER: NODE_ART_DIRECTOR,
    NODE_ART_DIRECTOR: NODE_CHARACTER_DESIGNER,
    NODE_CHARACTER_DESIGNER: NODE_STORYBOARD_ARTIST,
    NODE_STORYBOARD_ARTIST: NODE_ANIMATION_ARTIST,
    NODE_ANIMATION_ARTIST: NODE_SOUND_DIRECTOR,
    NODE_SOUND_DIRECTOR: NODE_COMPOSITOR,
    NODE_COMPOSITOR: NODE_END,
}


def route_from_director(state: ManjuState) -> str:
    if state["pending_feedback"]:
        return state["pending_feedback"][0]["target_node"]
    if state["approval_required"]:
        return NODE_DIRECTOR
    last_completed = state.get("route_reason") or ""
    if not last_completed:
        return NODE_SCRIPTWRITER
    return NODE_SEQUENCE.get(last_completed, NODE_SCRIPTWRITER)
