from create_batch_three import v
from common import read,save,digest
delivery=read(v.RELEASE/'batch3_hand_grip_delivery.json');log=v.RELEASE/'hand_source_transition.log'
if 'black_start:0.433 black_end:0.617' not in log.read_text():raise ValueError('Original-source transition was not verified')
save(v.RELEASE/'source_transition_evidence/batch3_hand_grip.json',{
    'output_sha256':delivery['sha256'],'output_intervals':[[12.429067,12.612589]],
    'source_sha256':v.GameStore().recording()['sha256'],'source_interval':[9409.433,9409.617],
    'source_log':str(log),'source_log_sha256':digest(log),
    'verification':'The original cropped recording has the same 0.184-second hand-inspection UI blink, within one frame of the export. It is not missing render footage.'})
