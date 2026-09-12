// Pure summarizer for ManagerDashboard.js -- counts pending items across
// the three lists a manager can act on (fetchLeaveRequests/fetchResignations/
// fetchOvertime, all already used by the existing admin screens this
// dashboard links out to). Kept separate from the screen itself so this
// logic is unit-testable without rendering (screens/components are
// deliberately excluded from this project's test coverage -- see
// package.json's collectCoverageFrom).
function countPending(items) {
  if (!Array.isArray(items)) return 0;
  return items.filter((item) => (item?.status || '').toLowerCase() === 'pending').length;
}

export function summarizePendingCounts({ leaves, resignations, overtime } = {}) {
  const leaveCount = countPending(leaves);
  const resignationCount = countPending(resignations);
  const overtimeCount = countPending(overtime);
  return {
    leaves: leaveCount,
    resignations: resignationCount,
    overtime: overtimeCount,
    total: leaveCount + resignationCount + overtimeCount,
  };
}
