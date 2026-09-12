// Pure decision logic for App.js's RootNavigator -- which post-login
// navigator tree a given `user` (AuthContext.js's shape) should mount.
// Extracted out of App.js so this branch can be unit-tested directly
// (matching this codebase's convention: screens/navigators aren't
// rendered in tests -- see package.json's collectCoverageFrom -- but the
// decision logic that picks between them can and should be).
//
// 'manager' is a real, distinct admin_users.role value the web backend
// already recognizes for leave/resignation/overtime approval
// (_LEAVE_APPROVER_ROLES in blueprints/leave.py), but until now nothing
// in the mobile client checked for it -- a manager login fell through to
// the same branch as 'admin'/'hr' and got the full AdminDrawerNavigator,
// including screens (Employees, Payroll, Seats & Billing, Settings
// toggles) a manager has no real access to server-side.
export function getNavigatorKey(user) {
  if (!user) return null;
  if (user.role === "admin" && user.adminRole === "manager") return "manager";
  if (user.role === "admin") return "admin";
  if (user.role === "employee") return "employee";
  return null;
}
