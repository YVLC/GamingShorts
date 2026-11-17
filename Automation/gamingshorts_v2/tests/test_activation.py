"""Configured-original activation and watcher ownership regressions."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import common
import full_game

class ActivationTests(unittest.TestCase):
    def test_relative_source_uses_runtime_root(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(common, 'config', return_value={'root':temp,'active_source':'Sources/videoplayback.webm'}):
                self.assertEqual(common.configured_source(), Path(temp)/'Sources/videoplayback.webm')

    def test_configured_source_can_register_without_move(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'Sources/videoplayback.webm'
            source.parent.mkdir(); source.write_bytes(b'fixture')
            proof={'probe':{'streams':[{'codec_type':'video','width':3840,'height':2160,'avg_frame_rate':'60/1'}]}}
            with patch.object(full_game.gs,'ROOT',Path(temp)), patch.object(full_game,'configured_source',return_value=source), patch('job_store.JobStore') as queue, patch.object(full_game,'GameStore') as store, patch.object(full_game,'seed_bridge_exclusion'):
                queue.return_value.admit_source.return_value=proof
                full_game.register('cairn','Cairn',source)
                store.return_value.register.assert_called_once_with('cairn','Cairn',proof)
                self.assertEqual(source.read_bytes(),b'fixture')

    def test_other_sources_still_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(full_game.gs,'ROOT',Path(temp)), patch.object(full_game,'configured_source',return_value=Path(temp)/'Sources/active.webm'):
                with self.assertRaises(ValueError):
                    full_game.register('cairn','Cairn',Path(temp)/'Sources/other.webm')
    def test_estimate_defers_strict_registration(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'source.webm'
            with patch.object(full_game,'configured_source',return_value=source), patch.object(full_game.gs,'probe',return_value={'format':{'duration':'100'}}), patch.object(full_game,'register') as register:
                store=__import__('unittest.mock',fromlist=['Mock']).Mock()
                store.recording.side_effect=ValueError('No active game')
                result=full_game.active_recording(store)
                self.assertEqual(result['status'],'configured_pending_strict_registration')
                register.assert_not_called()

    def test_explicit_start_registers_and_selects(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'source.webm'
            with patch.object(full_game,'configured_source',return_value=source), patch.object(full_game,'config',return_value={'active_game':'cairn'}), patch.object(full_game,'register') as register:
                store=__import__('unittest.mock',fromlist=['Mock']).Mock()
                store.recording.side_effect=ValueError('No active game')
                full_game.active_recording(store,start=True)
                register.assert_called_once_with('cairn','Cairn',source)
                store.select.assert_called_once_with('cairn')
