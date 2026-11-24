from dataclasses import replace

from ..model import Transaction
from .catalog import bind, replace_entry


def gap_actions(case, template, profile, prefix):
    for index in range(max(1, prefix), len(case.transactions)):
        tx = case.transactions[index]
        if template.name == "shorten_gap":
            waits = (tx.wait - 1, tx.wait // 2)
        else:
            waits = (tx.wait + 1, min(profile.max_wait, max(2, 2 * tx.wait)))
        for wait in dict.fromkeys(waits):
            if wait == tx.wait or not 0 <= wait <= profile.max_wait:
                continue
            updated = replace_entry(case.transactions, index, replace(tx, wait=wait))
            def fixed_wait(candidate, i=index, w=wait):
                return i < len(candidate.transactions) and candidate.transactions[i].wait == w
            yield bind(template, replace(case, transactions=updated), index, (index, wait), fixed_wait, wait_slot=index)


def edit_sequence(case, template, index, remove, added, operands):
    transactions = case.transactions[:index] + added + case.transactions[index + remove:]
    shift = len(added) - remove
    controls = tuple(
        replace(item, anchor=item.anchor + shift) if item.anchor >= index + remove else item
        for item in case.controls
    )
    updated = replace(case, transactions=transactions, controls=controls)
    values = tuple(tx.value for tx in transactions)
    def fixed_values(candidate):
        return tuple(tx.value for tx in candidate.transactions) == values
    return bind(template, updated, index, operands, fixed_values, shift_from=index)


def suffix_actions(case, template, profile, prefix):
    txs = case.transactions
    if template.name == "delete_transaction":
        anchors = {control.anchor for control in case.controls}
        for index in range(prefix, len(txs)):
            if index not in anchors:
                yield edit_sequence(case, template, index, 1, (), (index,))
        return
    if len(txs) >= profile.max_transactions:
        return
    if template.name == "duplicate_transaction":
        for index in range(prefix, len(txs)):
            yield edit_sequence(case, template, index + 1, 0, (txs[index],), (index, index + 1))
        return
    for index in range(prefix, len(txs) + 1):
        values = [0, 1]
        if index:
            values.append(txs[index - 1].value)
        if index < len(txs):
            values.append(txs[index].value)
        for value in dict.fromkeys(values):
            yield edit_sequence(case, template, index, 0, (Transaction(value),), (index, value))
