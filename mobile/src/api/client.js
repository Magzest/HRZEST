import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_BASE_URL } from '../config';

const client = axios.create({ baseURL: API_BASE_URL, timeout: 10000 });

client.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response && error.response.status === 401) {
      await AsyncStorage.multiRemove(['token', 'user_role', 'user_id']);
    }
    return Promise.reject(error);
  }
);

// ── Admin API ──────────────────────────────────────────────────────
export const adminLogin = (username, password) =>
  client.post('/api/login', { username, password });

export const adminLogout = () => client.post('/api/logout');

export const createOrganisation = (company_name, subdomain, admin_username, admin_password, admin_email = '', signup_secret = '', company_logo = '') =>
  client.post('/api/create_org', {
    company_name,
    subdomain,
    admin_username,
    admin_password,
    admin_email,
    signup_secret,
    company_logo,
  });

export const fetchDashboard = () => client.get('/api/dashboard');

export const fetchEmployees = () => client.get('/api/employees');

// ── Admin: Mark Attendance ──────────────────────────────────────────
export const fetchAttendanceEmployees = (date) =>
  client.get('/api/bulk_mark_attendance', { params: { date } });

export const markAttendance = (date, records) =>
  client.post('/api/bulk_mark_attendance', { date, records });

export const fetchHolidays = () => client.get('/api/holidays');

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
export const editEmployee = (empId, employeeData) => client.post(`/api/employees/${empId}/edit`, employeeData);
export const deleteEmployee = (empId) => client.post(`/api/employees/${empId}/delete`);
export const forgotPassword = (email, role = 'employee') => client.post('/api/forgot-password', { email, role });
export const resetPassword = (email, token, new_password, role = 'employee') => client.post('/api/reset-password', { email, token, new_password, role });
export const verifyMfaOtp = (otpCode) => client.post('/api/mfa/verify', { otp: otpCode });
export const fetchAiHelpdeskResponse = (query) => client.post('/api/ai_hrms', { query });
export const addHoliday = (holidayData) => client.post('/api/holidays/add', holidayData);
export const deleteHoliday = (hid) => client.post(`/api/holidays/${hid}/delete`);
export const compoffAction = (cid, action) => client.post(`/api/compoff/${cid}/action`, { action });
export const updateSettings = (settingsData) => client.post('/api/settings/update', settingsData);

// ── Additional Parity APIs ──────────────────────────────────────────
export const sendPayslipEmail = (empId, year, month) =>
  client.post('/api/payroll/send_payslip', { employee_id: empId, year, month });

export const lockPayroll = (year, month, status = true) =>
  client.post('/api/payroll/lock', { year, month, status });

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

