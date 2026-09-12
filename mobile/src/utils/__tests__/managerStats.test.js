import { summarizePendingCounts } from '../managerStats';

describe('summarizePendingCounts', () => {
  it('counts only Pending-status items per list, case-insensitively', () => {
    const result = summarizePendingCounts({
      leaves: [{ status: 'Pending' }, { status: 'Approved' }, { status: 'pending' }],
      resignations: [{ status: 'Declined' }],
      overtime: [{ status: 'Pending' }, { status: 'Pending' }],
    });
    expect(result).toEqual({ leaves: 2, resignations: 0, overtime: 2, total: 4 });
  });

  it('treats missing/empty lists as zero rather than throwing', () => {
    expect(summarizePendingCounts({})).toEqual({ leaves: 0, resignations: 0, overtime: 0, total: 0 });
    expect(summarizePendingCounts()).toEqual({ leaves: 0, resignations: 0, overtime: 0, total: 0 });
  });

  it('ignores non-array input for a single list instead of crashing', () => {
    expect(summarizePendingCounts({ leaves: null, resignations: undefined, overtime: 'not-a-list' }))
      .toEqual({ leaves: 0, resignations: 0, overtime: 0, total: 0 });
  });

  it('tolerates items with no status field', () => {
    expect(summarizePendingCounts({ leaves: [{}, { status: 'Pending' }] }))
      .toEqual({ leaves: 1, resignations: 0, overtime: 0, total: 1 });
  });
});
