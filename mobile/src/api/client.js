import axios from 'axios';
import { API_BASE_URL } from '../config';
import { secureGetItem } from '../utils/secureStorage';

const client = axios.create({ baseURL: API_BASE_URL, timeout: 10000 });

client.interceptors.request.use(async (config) => {
  const token = await secureGetItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// AuthContext registers a handler here so a genuinely dead session (the
// Bearer token expired/was revoked) clears storage and bounces the user
// back to login instead of leaving them stuck.
//
// Deliberately NOT wired to every 401 in the app: several endpoints 401 for
// reasons that have nothing to do with the session being dead -- wrong
// token type for that route, a feature endpoint that still expects a
// session cookie, etc. Auto-logging out on any of those would silently
// kill a perfectly valid session over an unrelated background call, which
// is exactly why we don't do that here. Instead, only 401s from the calls
// that establish "is my session even alive" (the dashboards' own initial
// load) are treated as fatal.
const SESSION_CRITICAL_PATHS = ['/api/dashboard', '/api/employee/portal'];

let unauthorizedHandler = null;
export const setUnauthorizedHandler = (handler) => {
  unauthorizedHandler = handler;
};

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error?.response?.status;
    if (status === 401) {
      const url = error?.config?.url || '';
      const isSessionCritical = SESSION_CRITICAL_PATHS.some((p) => url.includes(p));
      if (isSessionCritical && unauthorizedHandler) {
        unauthorizedHandler();
      }
    }
    return Promise.reject(error);
  }
);

// ── Admin API ──────────────────────────────────────────────────────
export const adminLogin = (username, password) =>
  client.post('/api/login', { username, password });

export const adminLogout = () => client.post('/api/logout');

export const fetchDashboard = () => client.get('/api/dashboard');

export const fetchEmployees = () => client.get('/api/employees');

// ── Admin: Mark Attendance ──────────────────────────────────────────
export const fetchAttendanceEmployees = (date) =>
  client.get('/api/bulk_mark_attendance', { params: { date } });

export const markAttendance = (date, records) =>
  client.post('/api/bulk_mark_attendance', { date, records });

export const fetchHolidays = () => client.get('/api/holidays');

export const fetchShifts = () => client.get('/api/shifts');

export const createShift = (name, start_time, half_time, end_time) =>
  client.post('/api/shifts', { name, start_time, half_time, end_time });

export const deleteShift = (sid) => client.delete(`/api/shifts/${sid}`);

export const assignShift = (emp_id, shift_id) =>
  client.post('/api/shifts/assign', { emp_id, shift_id });

export const fetchMonthlyReport = (year, month) =>
  client.get('/api/monthly_report', { params: { year, month } });

export const fetchSalaryReport = (year, month) =>
  client.get('/api/salary_report', { params: { year, month } });

export const fetchLeaveRequests = () => client.get('/api/leave_requests');

export const leaveAction = (lid, action) =>
  client.post(`/api/leave_requests/${lid}/action`, { action });

export const fetchResignations = () => client.get('/api/resignation_requests');

export const resignationAction = (rid, action) =>
  client.post(`/api/resignation_requests/${rid}/action`, { action });

export const fetchOvertime = () => client.get('/api/overtime');

export const fetchCompOff = () => client.get('/api/compoff');

export const fetchPerformance = () => client.get('/api/performance');

export const fetchOnboarding = () => client.get('/api/onboarding');

export const fetchDepartments = () => client.get('/api/departments');

// ── Employee API ───────────────────────────────────────────────────
export const employeeLogin = (employee_id, password) =>
  client.post('/api/employee/login', { employee_id, password });

export const employeeSignup = (employee_id, name, password, email = '', role = 'Employee', department = 'Engineering') =>
  client.post('/api/employee/signup', {
    employee_id,
    name,
    password,
    email,
    role,
    department,
  });

export const changePassword = (current_password, new_password) =>
  client.post('/api/employee/change-password', { current_password, new_password });

export const uploadEmployeePhoto = (formData) =>
  client.post('/api/employee/photo', formData, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 30000 });

export const qrFaceCheckin = (formData) =>
  client.post('/api/employee/qr-face-checkin', formData, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 30000 });

export const getAuthConfig = () =>
  client.get('/api/employee/auth-config');

export const getMobileBiometricNonce = () =>
  client.post('/api/employee/mobile-biometric-nonce');

export const attestMobileBiometric = (nonce) =>
  client.post('/api/employee/mobile-biometric-attest', { nonce });

export const attendanceCheckin = (formData) =>
  client.post('/api/employee/qr-face-checkin', formData, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 30000 });

export const getPhotoUrl = (empId) => `${API_BASE_URL}/dataset/${empId}.jpg`;

export const employeeLogout = () => client.post('/api/employee/logout');

export const fetchEmployeePortal = () => client.get('/api/employee/portal');

export const employeeCheckin = (lat, lon) =>
  client.post('/api/employee/checkin', { lat, lon });

export const syncOfflinePunches = (punches) =>
  client.post('/api/employee/sync_punches', { punches });

export const submitLeaveRequest = (leave_date, reason) =>
  client.post('/api/employee/leave_request', { leave_date, reason });

export const submitResignation = (last_working_day, reason) =>
  client.post('/api/employee/resign', { last_working_day, reason });

export const fetchEmployeeTickets = () => client.get('/api/employee/tickets');

export const raiseTicket = (category, subject, description, priority) =>
  client.post('/api/employee/raise_ticket', { category, subject, description, priority });

// ── Admin: Tickets ─────────────────────────────────────────────────
export const fetchAllTickets = () => client.get('/api/tickets');

export const ticketAction = (tid, status, admin_response) =>
  client.post(`/api/tickets/${tid}/action`, { status, admin_response });

export const fetchEmployeeSalary = (year, month) =>
  client.get('/api/employee/salary', { params: { year, month } });

export const fetchEmployeeAttendance = (year, month) =>
  client.get('/api/employee/attendance', { params: { year, month } });

export const fetchEmployeeLeaves = () => client.get('/api/employee/leaves');

export const cancelLeaveRequest = (lid) =>
  client.post(`/api/employee/cancel_leave/${lid}`);

export const requestOvertime = (date, reason) =>
  client.post('/api/employee/request_overtime', { date, reason });

export const fetchMyOvertime = () => client.get('/api/employee/my_overtime');

export const fetchEmployeeHolidays = () => client.get('/api/employee/holidays');

export const fetchEmployeeProfile = () => client.get('/api/employee/profile');

// ── Notifications ──────────────────────────────────────────────────
export const fetchNotifications = () => client.get('/api/notifications');
export const markNotificationsRead = () => client.post('/api/notifications/mark_read');
export const fetchEmployeeNotifications = () => client.get('/api/employee/notifications');
export const markEmployeeNotificationsRead = () => client.post('/api/employee/notifications/mark_read');

// ── Admin: Staff & Settings & AI ──────────────────────────────────
export const addEmployee = (employeeData) =>
  client.post('/api/employee/signup', {
    employee_id: (employeeData.employee_id || employeeData.emp_id || '').toUpperCase(),
    name: employeeData.name,
    password: employeeData.password || 'welcome123',
    email: employeeData.email,
    role: employeeData.role || 'Software Engineer',
    department: employeeData.department || 'Engineering',
  });
// editEmployee, deleteEmployee, forgotPassword, resetPassword, addHoliday,
// deleteHoliday were removed -- their routes (/api/employees/<id>/edit,
// /api/employees/<id>/delete, /api/forgot-password, /api/reset-password,
// /api/holidays/add, /api/holidays/<id>/delete) don't exist anywhere in
// the backend, Bearer or session-based, and none had a mobile caller left
// after removing the broken UI that used them.
export const fetchAiHelpdeskResponse = (query) => client.post('/api/ai/hr-helpdesk', { query });
export const compoffAction = (cid, action) => client.post(`/api/compoff/${cid}/action`, { action });
export const updateSettings = (settingsData) => client.post('/api/settings/update', settingsData);

// ── Additional Parity APIs ──────────────────────────────────────────
export const sendPayslipEmail = (empId, year, month) =>
  client.post('/api/send_salary_email', { emp_id: empId, year, month });

export const submitPerformanceReview = (empId, rating, comments, hike_percentage = 0, bonus = 0) =>
  client.post('/api/performance/review', { employee_id: empId, rating, comments, hike_percentage, bonus });

export const createOnboardingTask = (title, description, role = 'All') =>
  client.post('/api/onboarding/template/add', { title, description, role });

export const updateOnboardingTaskStatus = (taskId, status) =>
  client.post(`/api/onboarding/task/${taskId}/update`, { status });

export const uploadDocument = (formData) =>
  client.post('/api/employee/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30000,
  });

export const fetchEmployeeDocuments = () => client.get('/api/employee/documents');

export const broadcastNotification = (title, message, audience = 'all') =>
  client.post('/api/notifications/broadcast', { title, message, audience });

export const submitAttendanceRegularization = (date, reason, punch_in = '', punch_out = '') =>
  client.post('/api/employee/regularization', { date, reason, punch_in, punch_out });

export const addDepartment = (name, code = '') =>
  client.post('/api/departments/add', { name, code });

export const deleteDepartment = (deptId) =>
  client.post(`/api/departments/${deptId}/delete`);

// ── Seats & Billing ───────────────────────────────────────────────
// Employee-count-vs-plan-limit + monthly auto-debit status -- same
// underlying data as the web app's Seats & Billing page
// (templates/seat_checkout.html), served here as JSON.
export const fetchBillingStatus = () => client.get('/api/billing_status');

// Buying seats / enabling auto-debit needs Razorpay Checkout, which this
// app doesn't embed natively -- instead we bridge the current Bearer
// session into a one-time web session-cookie login and open that URL in
// an in-app WebView (see SeatsBillingScreen). The link is single-use and
// expires in 5 minutes.
export const getWebSessionLink = () => client.post('/api/mobile/web_session_link');

