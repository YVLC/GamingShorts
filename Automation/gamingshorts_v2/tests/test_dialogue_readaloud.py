"""Reading schedule must cover late dialogue without cutting or overlapping speech."""
import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tools'))
from repair_dialogue_readaloud import reading_segments,place_readings

class ReadingTests(unittest.TestCase):
    def test_every_line_including_late_payoff_has_real_words(self):
        lines=[dict(text='Hello there!',start=105,end=107),dict(text='Last line.',start=115,end=117)]
        words=[dict(word=w,start=a,end=a+.3) for w,a in [('Hello',.2),('there',.6),('Last',1.2),('line',1.6)]]
        segments=reading_segments(lines,words)
        schedule=place_readings(segments,100,2)
        self.assertEqual(len(schedule),2)
        self.assertEqual(schedule[-1]['placement'],15)
        self.assertEqual(schedule[-1]['words'][-1]['word'],'line.')

    def test_overflow_delays_next_reading_without_truncation(self):
        lines=[dict(start=5,words=[dict(start=0,end=4)]),dict(start=6,words=[dict(start=5,end=7)])]
        schedule=place_readings(lines,0,2)
        self.assertGreater(schedule[1]['placement'],schedule[0]['placement']+4)
        self.assertAlmostEqual(schedule[1]['cut_end']-schedule[1]['cut_start'],2.07)

    def test_missing_words_rejected(self):
        with self.assertRaises(ValueError):reading_segments([dict(text='Complete last line')],[dict(word='Complete',start=0,end=.5)])

if __name__=='__main__':unittest.main()
