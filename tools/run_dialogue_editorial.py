"""Continue the same Cairn mission under the user-authorized editorial repair."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from dialogue_mission import continue_mission
if __name__=='__main__':continue_mission()
