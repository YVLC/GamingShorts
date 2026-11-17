"""Contact sheet of actual extracted crop frames, for framing inspection."""
import sys,subprocess
from pathlib import Path
p=Path(sys.argv[1]);files=sorted(p.glob('shot_*.jpg'))
subprocess.run(['ffmpeg','-v','error','-y','-pattern_type','glob','-i',str(p/'shot_*.jpg'),
    '-vf',f'scale=270:480,tile=3x{(len(files)+2)//3}',
    '-frames:v','1',str(p/'contact_sheet.jpg')],check=True)
