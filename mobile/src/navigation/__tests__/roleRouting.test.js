import { getNavigatorKey } from '../roleRouting';

describe('getNavigatorKey', () => {
  it('returns null when there is no user (logged out)', () => {
    expect(getNavigatorKey(null)).toBe(null);
    expect(getNavigatorKey(undefined)).toBe(null);
  });

  it('routes a plain admin to the admin navigator', () => {
    expect(getNavigatorKey({ role: 'admin', adminRole: 'admin' })).toBe('admin');
  });

  it('routes an HR-role admin to the admin navigator (unchanged behavior)', () => {
    expect(getNavigatorKey({ role: 'admin', adminRole: 'hr' })).toBe('admin');
  });

  it('routes a manager-role admin to the manager navigator', () => {
    expect(getNavigatorKey({ role: 'admin', adminRole: 'manager' })).toBe('manager');
  });

  it('routes an employee to the employee navigator', () => {
    expect(getNavigatorKey({ role: 'employee' })).toBe('employee');
  });

  it('falls back to admin when adminRole is missing entirely (defensive)', () => {
    expect(getNavigatorKey({ role: 'admin' })).toBe('admin');
  });

  it('returns null for an unrecognized role rather than guessing', () => {
    expect(getNavigatorKey({ role: 'something_new' })).toBe(null);
  });
});
