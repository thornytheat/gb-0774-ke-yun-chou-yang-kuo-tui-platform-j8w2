import pytest

from app.config import TRANSFER_TYPES
from app.errors import SurveyProblem
from app.modules.allocation.remainders import split_transfer
from app.modules.frame.join import classify
from app.modules.frame.register import versions
from app.modules.returns.service import collect

FRAME = (
    'trip,revision,layer,tickets\n'
    '0001,1,枢纽,120\n'
    '0002,1,城北,80\n'
)
HEADER = 'ticket,trip,reported_layer,visit,status,probability,choice\n'


def run_with(returns, frame=FRAME):
    from app.pipeline import run
    return run({'returns': HEADER + returns, 'frame': frame})


# 旧问卷只写 transfer 的两张票 + 新问卷带类型的票，同票同概率便于核对权重。
BASE = (
    '00010,0001,枢纽,1,YES,1/2,direct\n'
    '00011,0001,枢纽,1,YES,1/3,transfer\n'
    '00012,0001,枢纽,1,YES,1/3,transfer\n'
    '00013,0001,枢纽,1,YES,1/6,transfer_bus\n'
    '00021,0002,城北,1,YES,1/2,transfer_rail\n'
    '00022,0002,城北,1,YES,1/4,other\n'
)


def test_legacy_transfer_kept_untyped_not_guessed():
    result = run_with(BASE)
    ledger = result['balance']['transfer_types']
    assert ledger['known'] + ledger['untyped'] == result['allocation']['totals']['transfer']
    assert ledger['total_delta'] == 0 and ledger['balanced'] is True
    # 旧答卷两票全部进「类型未补」，公交/轨道不得被猜配。
    assert result['balance']['strata']['枢纽']['transfer']['observed'] == {
        'transfer': 2, 'transfer_bus': 1, 'transfer_rail': 0}


def test_typed_transfer_still_counts_as_transfer_for_dispatch():
    result = run_with(BASE)
    valid = {row['ticket']: row for row in result['frame']['valid']}
    assert valid['00013']['choice'] == 'transfer'
    assert valid['00013']['transfer_type'] == 'transfer_bus'
    assert valid['00021']['choice'] == 'transfer'
    assert valid['00021']['transfer_type'] == 'transfer_rail'
    assert set(result['weights']['layers']['枢纽']['quotas']) == {'direct', 'transfer', 'other'}


def test_layer_ledger_reconciles_exact_and_integer():
    result = run_with(BASE)
    from fractions import Fraction
    for name, row in result['balance']['strata'].items():
        sub_quota = sum(Fraction(v) for v in row['transfer']['quotas'].values())
        assert sub_quota == Fraction(result['weights']['layers'][name]['quotas']['transfer'])
        assert sum(row['transfer']['integers'].values()) == result['allocation']['layers'][name]['integers']['transfer']
        assert row['transfer']['integer_delta'] == 0 and row['transfer']['quota_delta'] == '0'
    assert result['balance']['balanced'] is True


def test_late_followup_type_only_keeps_weight_and_layer_transfer_total():
    before = run_with(BASE)
    # 补访只把 00011 的换乘类型补成轨道，概率、班次、状态全部照旧。
    followup = BASE + '00011,0001,枢纽,2,YES,1/3,transfer_rail\n'
    after = run_with(followup)

    def ticket_weight(output, ticket):
        for layer in output['weights']['layers'].values():
            for row in layer['rows']:
                if row['ticket'] == ticket:
                    return row['base'], row['calibrated']
        raise AssertionError(ticket)

    assert ticket_weight(after, '00011') == ticket_weight(before, '00011')
    # 各层换乘精确配额、换乘整数总人数照旧。
    for name in before['weights']['layers']:
        assert after['weights']['layers'][name]['quotas']['transfer'] == \
            before['weights']['layers'][name]['quotas']['transfer']
        assert after['allocation']['layers'][name]['integers']['transfer'] == \
            before['allocation']['layers'][name]['integers']['transfer']
    # 变化只发生在已知/未知分层之间：轨道 +1 票的权重，未补相应减少。
    assert after['balance']['strata']['枢纽']['transfer']['observed'] == {
        'transfer': 1, 'transfer_bus': 1, 'transfer_rail': 1}
    assert after['balance']['transfer_types']['known'] + after['balance']['transfer_types']['untyped'] \
        == after['allocation']['totals']['transfer']
    assert after['balance']['transfer_types']['total_delta'] == 0


def test_transfer_integer_split_conserves_total():
    # 三类型精确配额合计等于换乘精确配额 100/3，整数分配后仍守恒。
    quotas = {'transfer': '100/9', 'transfer_bus': '100/9', 'transfer_rail': '100/9'}
    split = split_transfer(quotas, 33)
    assert sum(split['integers'].values()) == 33
    assert set(split['integers']) == set(TRANSFER_TYPES)


def test_unknown_transfer_code_rejected_not_silently_bucketed():
    trips = versions(FRAME)
    intake = collect(HEADER + '00014,0001,枢纽,1,YES,1/2,transfer_air\n')
    record = intake['accepted'][0]
    row = classify(record, trips)
    assert row['code'] == 'BAD_RESPONSE'


def test_same_visit_conflicting_transfer_type_isolated():
    text = HEADER + (
        '00031,0002,城北,1,YES,1/2,transfer_bus\n'
        '00031,0002,城北,1,YES,1/2,transfer_rail\n'
    )
    intake = collect(text)
    assert intake['reasons'] == {'VISIT_CONFLICT': 2} and intake['accepted'] == []


def test_rerun_same_batch_adds_no_archive(tmp_path):
    from app.main import create_app
    client = create_app(tmp_path / 'typed.db').test_client()
    body = {'tables': {'returns': HEADER + BASE, 'frame': FRAME}}
    first = client.post('/api/runs', json=body)
    assert first.status_code == 201
    key = first.json['id']
    second = client.post(f'/api/runs/{key}/rerun')
    assert second.status_code == 200 and second.json['reused'] is True
    assert second.json['id'] == key
    runs = client.get('/api/runs').json['runs']
    assert len(runs) == 1
    # 旧档结果仍可原样复算，含换乘分层留档。
    fetched = client.get(f'/api/runs/{key}').json
    assert fetched['balance']['transfer_types']['balanced'] is True
