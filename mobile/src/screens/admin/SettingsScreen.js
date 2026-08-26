import React, { useState, useEffect } from "react";
import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
  View,
  Text,
  TouchableOpacity,
  TextInput,
  Switch,
  Alert,
  Modal,
  ActivityIndicator,
} from "react-native";
import { DrawerActions } from "@react-navigation/native";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";

import AdminHeader from "../../components/admin/AdminHeader";
import THEME from "../../constants/theme";
import { useAuth } from "../../store/AuthContext";
import {
  fetchShifts, createShift, fetchSettings, saveCompanySettings, saveGeoRadius,
  toggleCompanyFeature, fetchAdminProfile, changeAdminPassword,
} from "../../api/client";

// company_settings.working_days is a free-form CSV of day abbreviations
// (e.g. "Mon,Tue,Wed,Thu,Fri"), but this screen's UI is a simpler 3-chip
// picker -- these two maps translate between them so the picker can stay
// simple while still round-tripping the real column faithfully.
const WORKING_DAYS_OPTIONS = {
  "Mon - Fri": "Mon,Tue,Wed,Thu,Fri",
  "Mon - Sat": "Mon,Tue,Wed,Thu,Fri,Sat",
  "All 7 Days": "Mon,Tue,Wed,Thu,Fri,Sat,Sun",
};
const workingDaysCsvToLabel = (csv) => {
  const set = new Set((csv || "").split(",").map((d) => d.trim()).filter(Boolean));
  if (set.size === 7) return "All 7 Days";
  if (set.size === 6 && set.has("Sat")) return "Mon - Sat";
  return "Mon - Fri";
};

export default function SettingsScreen({ navigation, route }) {
  const { signOut } = useAuth();

  // Tab State: 'company' | 'shifts' | 'attendance' | 'security' | 'notifications' | 'payroll' | 'profile'
  const initialTab = route?.params?.tab || "company";
  const [activeTab, setActiveTab] = useState(initialTab);

  useEffect(() => {
    if (route?.params?.tab) {
      setActiveTab(route.params.tab);
    }
  }, [route?.params?.tab]);

  // Form States - Company -- real values loaded from GET /api/settings
  // below (empty/neutral until then, not fabricated placeholder text).
  const [companyName, setCompanyName] = useState("");
  const [companyCode, setCompanyCode] = useState("");
  const [timezone, setTimezone] = useState("Asia/Kolkata");
  const [workingDays, setWorkingDays] = useState("Mon - Fri");
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [savingCompany, setSavingCompany] = useState(false);
  const [savingAttendance, setSavingAttendance] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);

  // Admin Profile -- real values from GET /api/admin/profile.
  const [profileUsername, setProfileUsername] = useState("");
  const [profileEmail, setProfileEmail] = useState("");
  const [profileRole, setProfileRole] = useState("admin");
  const [profileCreatedAt, setProfileCreatedAt] = useState("");

  // Shifts -- real data from /api/shifts (Bearer-compatible), not the
  // hardcoded 3-shift list this used to show regardless of what actually
  // existed in the database.
  const [shifts, setShifts] = useState([]);
  const [shiftsLoading, setShiftsLoading] = useState(false);
  const [gracePeriod, setGracePeriod] = useState("15");
  const [halfDayHours, setHalfDayHours] = useState("4.0");

  // Form States - Attendance & Geofence -- geofenceEnabled/faceRecog map to
  // real company_settings.geo_enabled/face_auth_enabled columns (toggled
  // instantly via /api/settings/toggle_feature, same as web); radius/lat/lon
  // map to geo_radius/office_lat/office_lon, saved via /api/settings/geo_radius.
  // livenessCheck/autoCheckout were removed -- neither has any backing
  // column anywhere in this codebase (web doesn't have them either), so
  // there was nothing for a Save button to actually persist.
  const [geofenceEnabled, setGeofenceEnabled] = useState(false);
  const [geofenceRadius, setGeofenceRadius] = useState("200");
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [faceRecog, setFaceRecog] = useState(false);

  // Form States - Security
  const [twoFactorActive, setTwoFactorActive] = useState(true);
  const [sessionTimeout, setSessionTimeout] = useState("30");
  const [ipWhitelist, setIpWhitelist] = useState(false);
  const [currentPass, setCurrentPass] = useState("");
  const [newPass, setNewPass] = useState("");
  const [confirmPass, setConfirmPass] = useState("");

  // Form States - Notifications -- match company_settings' real
  // notify_leave/notify_payslip/notify_resignation/notify_doc_expiry
  // columns exactly (same four events templates/settings.html's own
  // "Notification Triggers" section exposes), toggled instantly via
  // /api/settings/toggle_feature. The previous push/digest/late-alert
  // framing here had no corresponding column anywhere -- there was
  // nothing for those switches to actually turn on or off.
  const [notifyLeave, setNotifyLeave] = useState(false);
  const [notifyPayslip, setNotifyPayslip] = useState(false);
  const [notifyResignation, setNotifyResignation] = useState(false);
  const [notifyDocExpiry, setNotifyDocExpiry] = useState(false);

  // Form States - Payroll
  const [payDay, setPayDay] = useState("1");
  const [overtimeRate, setOvertimeRate] = useState("1.5");
  const [standardWorkingDays, setStandardWorkingDays] = useState("26");
  const [autoTax, setAutoTax] = useState(true);
  const [autoEmailPayslip, setAutoEmailPayslip] = useState(true);

  // Modal State for Adding Shift
  const [addShiftModal, setAddShiftModal] = useState(false);
  const [newShiftName, setNewShiftName] = useState("");
  const [newShiftStart, setNewShiftStart] = useState("09:00 AM");
  const [newShiftEnd, setNewShiftEnd] = useState("06:00 PM");

  const tabs = [
    { id: "company", label: "Company", icon: "business" },
    { id: "shifts", label: "Shifts", icon: "time" },
    { id: "attendance", label: "Attendance", icon: "location" },
    { id: "security", label: "Security", icon: "shield-checkmark" },
    { id: "notifications", label: "Alerts", icon: "notifications" },
    { id: "payroll", label: "Payroll", icon: "wallet" },
    { id: "profile", label: "Admin Profile", icon: "person" },
  ];

  // Payroll Rules has no Bearer (or even session-JSON) backend anywhere in
  // this codebase -- save_salary_rules is a much larger session-only form
  // than what's modeled here, so there's genuinely nothing yet to wire
  // this button to without inventing fields that don't exist.
  const handleSave = (sectionName) => {
    Alert.alert(
      "Not Available on Mobile Yet",
      `Saving ${sectionName.toLowerCase()} is only available from the web admin dashboard for now.`
    );
  };

  const loadSettingsAndProfile = async () => {
    setSettingsLoading(true);
    try {
      const [settingsRes, profileRes] = await Promise.all([
        fetchSettings().catch(() => null),
        fetchAdminProfile().catch(() => null),
      ]);
      const s = settingsRes?.data?.ok ? settingsRes.data.settings : null;
      if (s) {
        setCompanyName(s.company_name || "");
        setCompanyCode(s.company_code || "");
        setTimezone(s.timezone || "Asia/Kolkata");
        setWorkingDays(workingDaysCsvToLabel(s.working_days));
        setGeofenceEnabled(!!s.geo_enabled);
        setGeofenceRadius(s.geo_radius != null ? String(s.geo_radius) : "200");
        setLatitude(s.office_lat != null ? String(s.office_lat) : "");
        setLongitude(s.office_lon != null ? String(s.office_lon) : "");
        setFaceRecog(!!s.face_auth_enabled);
        setNotifyLeave(!!s.notify_leave);
        setNotifyPayslip(!!s.notify_payslip);
        setNotifyResignation(!!s.notify_resignation);
        setNotifyDocExpiry(!!s.notify_doc_expiry);
      }
      const p = profileRes?.data?.ok ? profileRes.data : null;
      if (p) {
        setProfileUsername(p.username || "");
        setProfileEmail(p.email || "");
        setProfileRole(p.role || "admin");
        setProfileCreatedAt(p.created_at || "");
      }
    } catch (_) {
      // Fail quiet -- fields just stay at their neutral defaults.
    } finally {
      setSettingsLoading(false);
    }
  };

  useEffect(() => {
    loadSettingsAndProfile();
  }, []);

  const handleSaveCompany = async () => {
    if (!companyName.trim()) {
      Alert.alert("Validation Error", "Company name is required.");
      return;
    }
    setSavingCompany(true);
    let res;
    try {
      res = await saveCompanySettings(
        companyName.trim(), companyCode.trim(), timezone, WORKING_DAYS_OPTIONS[workingDays]
      );
    } catch (e) {
      res = e?.response;
    }
    setSavingCompany(false);
    if (!res?.data?.ok) {
      Alert.alert("Save Failed", res?.data?.msg || "Could not save company info.");
      return;
    }
    Alert.alert("Saved", "Company info updated.");
  };

  // geo_enabled/face_auth_enabled/notify_* all save instantly on toggle,
  // same as web's toggle_feature -- optimistic update with rollback on
  // failure rather than a separate "Save" step for a single switch.
  const handleToggleFeature = async (feature, value, setter) => {
    setter(value);
    let res;
    try {
      res = await toggleCompanyFeature(feature, value);
    } catch (e) {
      res = e?.response;
    }
    if (!res?.data?.ok) {
      setter(!value);
      Alert.alert("Update Failed", res?.data?.msg || "Could not update this setting.");
    }
  };

  const handleSaveAttendance = async () => {
    const radiusNum = parseInt(geofenceRadius, 10);
    if (!radiusNum || radiusNum < 50 || radiusNum > 5000) {
      Alert.alert("Validation Error", "Geofence radius must be between 50 and 5000 metres.");
      return;
    }
    setSavingAttendance(true);
    let res;
    try {
      res = await saveGeoRadius(radiusNum, latitude.trim(), longitude.trim());
    } catch (e) {
      res = e?.response;
    }
    setSavingAttendance(false);
    if (!res?.data?.ok) {
      Alert.alert("Save Failed", res?.data?.msg || "Could not save attendance settings.");
      return;
    }
    Alert.alert("Saved", "Attendance settings updated.");
  };

  const handleChangePassword = async () => {
    if (!currentPass || !newPass || !confirmPass) {
      Alert.alert("Validation Error", "Please fill in all password fields.");
      return;
    }
    if (newPass !== confirmPass) {
      Alert.alert("Error", "New password and confirmation do not match.");
      return;
    }
    if (newPass.length < 8) {
      Alert.alert("Error", "New password must be at least 8 characters.");
      return;
    }
    setChangingPassword(true);
    let res;
    try {
      res = await changeAdminPassword(currentPass, newPass, confirmPass);
    } catch (e) {
      res = e?.response;
    }
    setChangingPassword(false);
    if (!res?.data?.ok) {
      Alert.alert("Change Failed", res?.data?.msg || "Could not change password.");
      return;
    }
    setCurrentPass("");
    setNewPass("");
    setConfirmPass("");
    Alert.alert("Success", "Your password was changed.");
  };

  // Converts a "09:00 AM" / "6:30 PM" style string (what this form collects)
  // into the 24-hour "HH:MM" the API expects (matches what /api/shifts GET
  // already returns, so the round-trip is consistent).
  const to24Hour = (t) => {
    const m = /^(\d{1,2}):(\d{2})\s*(AM|PM)$/i.exec(t.trim());
    if (!m) return t.trim();
    let [, h, min, period] = m;
    h = parseInt(h, 10);
    if (period.toUpperCase() === "PM" && h !== 12) h += 12;
    if (period.toUpperCase() === "AM" && h === 12) h = 0;
    return `${String(h).padStart(2, "0")}:${min}`;
  };

  const loadShifts = async () => {
    setShiftsLoading(true);
    try {
      const res = await fetchShifts();
      if (res?.data?.ok && Array.isArray(res.data.shifts)) {
        setShifts(res.data.shifts);
      }
    } catch (_) {}
    setShiftsLoading(false);
  };

  useEffect(() => {
    loadShifts();
  }, []);

  const handleAddShift = async () => {
    if (!newShiftName.trim()) {
      Alert.alert("Error", "Please enter shift name.");
      return;
    }
    try {
      const start24 = to24Hour(newShiftStart);
      const end24 = to24Hour(newShiftEnd);
      // No half-day time field in this form yet -- defaults to the
      // midpoint-ish 13:00, matching what the shift list already implies
      // as a typical half-day cutoff.
      const res = await createShift(newShiftName.trim(), start24, "13:00", end24);
      if (res?.data?.ok) {
        Alert.alert("Success", `Shift "${newShiftName}" created successfully!`);
        setAddShiftModal(false);
        setNewShiftName("");
        await loadShifts();
      } else {
        Alert.alert("Failed", res?.data?.msg || "Could not create shift.");
      }
    } catch (e) {
      Alert.alert("Failed", e?.response?.data?.msg || "Could not create shift.");
    }
  };

  return (
    <LinearGradient colors={["#F8FAFC", "#F1F5F9", "#E2E8F0"]} style={styles.container}>
      <SafeAreaView style={{ flex: 1 }}>
        <AdminHeader
          title="System Settings"
          onMenu={() => navigation.dispatch(DrawerActions.openDrawer())}
        />

        {/* Horizontal Navigation Tabs */}
        <View style={styles.tabBarContainer}>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.tabBarContent}
          >
            {tabs.map((tab) => {
              const isActive = activeTab === tab.id;
              return (
                <TouchableOpacity
                  key={tab.id}
                  activeOpacity={0.8}
                  style={[styles.tabButton, isActive && styles.tabButtonActive]}
                  onPress={() => setActiveTab(tab.id)}
                >
                  <Ionicons
                    name={tab.icon}
                    size={16}
                    color={isActive ? "#FFFFFF" : "#64748B"}
                  />
                  <Text style={[styles.tabText, isActive && styles.tabTextActive]}>
                    {tab.label}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        </View>

        {/* Tab Content Container */}
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.content}
        >
          {/* TAB 1: COMPANY INFO */}
          {activeTab === "company" && (
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <Ionicons name="business" size={22} color="#0B2253" />
                <Text style={styles.cardHeaderTitle}>Company & Organization Profile</Text>
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.label}>COMPANY NAME</Text>
                <TextInput
                  style={styles.input}
                  value={companyName}
                  onChangeText={setCompanyName}
                />
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.label}>COMPANY CODE</Text>
                <TextInput
                  style={styles.input}
                  value={companyCode}
                  onChangeText={setCompanyCode}
                />
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.label}>WORKING DAYS POLICY</Text>
                <View style={styles.daysToggleRow}>
                  {["Mon - Fri", "Mon - Sat", "All 7 Days"].map((option) => (
                    <TouchableOpacity
                      key={option}
                      style={[
                        styles.chipBtn,
                        workingDays === option && styles.chipBtnActive,
                      ]}
                      onPress={() => setWorkingDays(option)}
                    >
                      <Text
                        style={[
                          styles.chipText,
                          workingDays === option && styles.chipTextActive,
                        ]}
                      >
                        {option}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>

              <TouchableOpacity
                style={styles.saveButton}
                activeOpacity={0.8}
                onPress={handleSaveCompany}
                disabled={savingCompany}
              >
                {savingCompany ? (
                  <ActivityIndicator color="#FFF" />
                ) : (
                  <>
                    <Ionicons name="checkmark-circle-outline" size={18} color="#FFF" />
                    <Text style={styles.saveButtonText}>Save Profile Settings</Text>
                  </>
                )}
              </TouchableOpacity>
            </View>
          )}

          {/* TAB 2: SHIFTS & TIMINGS */}
          {activeTab === "shifts" && (
            <View style={styles.card}>
              <View style={styles.cardHeaderBetween}>
                <View style={{ flexDirection: "row", alignItems: "center" }}>
                  <Ionicons name="time" size={22} color="#0B2253" />
                  <Text style={[styles.cardHeaderTitle, { marginLeft: 8 }]}>Work Shifts & Grace Timings</Text>
                </View>
                <TouchableOpacity
                  style={styles.smallAddBtn}
                  onPress={() => setAddShiftModal(true)}
                >
                  <Ionicons name="add-circle" size={16} color="#0B2253" />
                  <Text style={styles.smallAddBtnText}>Add Shift</Text>
                </TouchableOpacity>
              </View>

              <View style={styles.twoCol}>
                <View style={[styles.inputGroup, { flex: 1, marginRight: 8 }]}>
                  <Text style={styles.label}>GRACE MINUTES</Text>
                  <TextInput
                    style={styles.input}
                    value={gracePeriod}
                    onChangeText={setGracePeriod}
                    keyboardType="numeric"
                  />
                </View>
                <View style={[styles.inputGroup, { flex: 1, marginLeft: 8 }]}>
                  <Text style={styles.label}>HALF-DAY HOURS</Text>
                  <TextInput
                    style={styles.input}
                    value={halfDayHours}
                    onChangeText={setHalfDayHours}
                    keyboardType="numeric"
                  />
                </View>
              </View>

              <Text style={[styles.label, { marginTop: 12, marginBottom: 10 }]}>ACTIVE SHIFTS SCHEDULE</Text>

              {shifts.map((s) => (
                <View key={s.id} style={styles.shiftCardItem}>
                  <View style={styles.shiftIconBox}>
                    <Ionicons name="alarm-outline" size={20} color="#0B2253" />
                  </View>
                  <View style={{ flex: 1, marginLeft: 12 }}>
                    <Text style={styles.shiftName}>{s.name}</Text>
                    <Text style={styles.shiftTiming}>
                      {s.start} — {s.end} (Half: {s.half})
                    </Text>
                  </View>
                  <View style={styles.activeTag}>
                    <Text style={styles.activeTagText}>Active</Text>
                  </View>
                </View>
              ))}

              <TouchableOpacity
                style={styles.saveButton}
                activeOpacity={0.8}
                onPress={() => handleSave("Shifts & Timings")}
              >
                <Ionicons name="checkmark-circle-outline" size={18} color="#FFF" />
                <Text style={styles.saveButtonText}>Update Shift Rules</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* TAB 3: ATTENDANCE & GEOFENCE */}
          {activeTab === "attendance" && (
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <Ionicons name="location" size={22} color="#0B2253" />
                <Text style={styles.cardHeaderTitle}>GPS Geofence & Facial Verification</Text>
              </View>

              <View style={styles.settingRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.settingRowTitle}>GPS Geofence Restriction</Text>
                  <Text style={styles.settingRowSub}>Limit check-in to office GPS radius</Text>
                </View>
                <Switch
                  value={geofenceEnabled}
                  onValueChange={(v) => handleToggleFeature("geo_enabled", v, setGeofenceEnabled)}
                  trackColor={{ false: "#CBD5E1", true: "#93C5FD" }}
                  thumbColor={geofenceEnabled ? "#0B2253" : "#F1F5F9"}
                />
              </View>

              {geofenceEnabled && (
                <>
                  <View style={styles.inputGroup}>
                    <Text style={styles.label}>GEOFENCE RADIUS (METERS)</Text>
                    <TextInput
                      style={styles.input}
                      value={geofenceRadius}
                      onChangeText={setGeofenceRadius}
                      keyboardType="numeric"
                    />
                  </View>

                  <View style={styles.twoCol}>
                    <View style={[styles.inputGroup, { flex: 1, marginRight: 8 }]}>
                      <Text style={styles.label}>LATITUDE</Text>
                      <TextInput
                        style={styles.input}
                        value={latitude}
                        onChangeText={setLatitude}
                      />
                    </View>
                    <View style={[styles.inputGroup, { flex: 1, marginLeft: 8 }]}>
                      <Text style={styles.label}>LONGITUDE</Text>
                      <TextInput
                        style={styles.input}
                        value={longitude}
                        onChangeText={setLongitude}
                      />
                    </View>
                  </View>
                </>
              )}

              <View style={styles.divider} />

              <View style={styles.settingRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.settingRowTitle}>Facial Recognition Matching</Text>
                  <Text style={styles.settingRowSub}>Verify employee selfie on check-in</Text>
                </View>
                <Switch
                  value={faceRecog}
                  onValueChange={(v) => handleToggleFeature("face_auth_enabled", v, setFaceRecog)}
                  trackColor={{ false: "#CBD5E1", true: "#93C5FD" }}
                  thumbColor={faceRecog ? "#0B2253" : "#F1F5F9"}
                />
              </View>

              <TouchableOpacity
                style={styles.saveButton}
                activeOpacity={0.8}
                onPress={handleSaveAttendance}
                disabled={savingAttendance}
              >
                {savingAttendance ? (
                  <ActivityIndicator color="#FFF" />
                ) : (
                  <>
                    <Ionicons name="checkmark-circle-outline" size={18} color="#FFF" />
                    <Text style={styles.saveButtonText}>Save Geofence Radius & Location</Text>
                  </>
                )}
              </TouchableOpacity>
            </View>
          )}

          {/* TAB 4: SECURITY */}
          {activeTab === "security" && (
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <Ionicons name="shield-checkmark" size={22} color="#0B2253" />
                <Text style={styles.cardHeaderTitle}>Security & Access Control</Text>
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.label}>SESSION INACTIVITY TIMEOUT (MINUTES)</Text>
                <TextInput
                  style={styles.input}
                  value={sessionTimeout}
                  onChangeText={setSessionTimeout}
                  keyboardType="numeric"
                />
              </View>

              <View style={styles.divider} />

              <Text style={[styles.cardHeaderTitle, { fontSize: 16, marginBottom: 14 }]}>Change Admin Password</Text>

              <View style={styles.inputGroup}>
                <Text style={styles.label}>CURRENT PASSWORD</Text>
                <TextInput
                  style={styles.input}
                  secureTextEntry
                  value={currentPass}
                  onChangeText={setCurrentPass}
                  placeholder="••••••••"
                />
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.label}>NEW PASSWORD</Text>
                <TextInput
                  style={styles.input}
                  secureTextEntry
                  value={newPass}
                  onChangeText={setNewPass}
                  placeholder="••••••••"
                />
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.label}>CONFIRM NEW PASSWORD</Text>
                <TextInput
                  style={styles.input}
                  secureTextEntry
                  value={confirmPass}
                  onChangeText={setConfirmPass}
                  placeholder="••••••••"
                />
              </View>

              <TouchableOpacity
                style={styles.saveButton}
                activeOpacity={0.8}
                onPress={handleChangePassword}
                disabled={changingPassword}
              >
                {changingPassword ? (
                  <ActivityIndicator color="#FFF" />
                ) : (
                  <>
                    <Ionicons name="key-outline" size={18} color="#FFF" />
                    <Text style={styles.saveButtonText}>Update Admin Password</Text>
                  </>
                )}
              </TouchableOpacity>
            </View>
          )}

          {/* TAB 5: NOTIFICATIONS */}
          {activeTab === "notifications" && (
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <Ionicons name="notifications" size={22} color="#0B2253" />
                <Text style={styles.cardHeaderTitle}>Notification Preferences & Alerts</Text>
              </View>

              <Text style={{ fontSize: 12, color: "#64748B", marginBottom: 4 }}>
                Choose which events send an email to admins. Each toggle saves immediately.
              </Text>

              <View style={styles.settingRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.settingRowTitle}>New Leave Request</Text>
                  <Text style={styles.settingRowSub}>When an employee submits a leave</Text>
                </View>
                <Switch
                  value={notifyLeave}
                  onValueChange={(v) => handleToggleFeature("notify_leave", v, setNotifyLeave)}
                  trackColor={{ false: "#CBD5E1", true: "#93C5FD" }}
                  thumbColor={notifyLeave ? "#0B2253" : "#F1F5F9"}
                />
              </View>

              <View style={styles.settingRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.settingRowTitle}>Payslip Sent</Text>
                  <Text style={styles.settingRowSub}>Confirmation when payslip is emailed</Text>
                </View>
                <Switch
                  value={notifyPayslip}
                  onValueChange={(v) => handleToggleFeature("notify_payslip", v, setNotifyPayslip)}
                  trackColor={{ false: "#CBD5E1", true: "#93C5FD" }}
                  thumbColor={notifyPayslip ? "#0B2253" : "#F1F5F9"}
                />
              </View>

              <View style={styles.settingRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.settingRowTitle}>Resignation Submitted</Text>
                  <Text style={styles.settingRowSub}>New resignation request received</Text>
                </View>
                <Switch
                  value={notifyResignation}
                  onValueChange={(v) => handleToggleFeature("notify_resignation", v, setNotifyResignation)}
                  trackColor={{ false: "#CBD5E1", true: "#93C5FD" }}
                  thumbColor={notifyResignation ? "#0B2253" : "#F1F5F9"}
                />
              </View>

              <View style={styles.settingRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.settingRowTitle}>Document Expiry Alert</Text>
                  <Text style={styles.settingRowSub}>Before employee documents expire</Text>
                </View>
                <Switch
                  value={notifyDocExpiry}
                  onValueChange={(v) => handleToggleFeature("notify_doc_expiry", v, setNotifyDocExpiry)}
                  trackColor={{ false: "#CBD5E1", true: "#93C5FD" }}
                  thumbColor={notifyDocExpiry ? "#0B2253" : "#F1F5F9"}
                />
              </View>
            </View>
          )}

          {/* TAB 6: PAYROLL RULES */}
          {activeTab === "payroll" && (
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <Ionicons name="wallet" size={22} color="#0B2253" />
                <Text style={styles.cardHeaderTitle}>Payroll & Compensation Rules</Text>
              </View>

              <View style={styles.twoCol}>
                <View style={[styles.inputGroup, { flex: 1, marginRight: 8 }]}>
                  <Text style={styles.label}>MONTHLY PAY DAY</Text>
                  <TextInput
                    style={styles.input}
                    value={payDay}
                    onChangeText={setPayDay}
                    keyboardType="numeric"
                  />
                </View>
                <View style={[styles.inputGroup, { flex: 1, marginLeft: 8 }]}>
                  <Text style={styles.label}>OT MULTIPLIER</Text>
                  <TextInput
                    style={styles.input}
                    value={overtimeRate}
                    onChangeText={setOvertimeRate}
                    keyboardType="numeric"
                  />
                </View>
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.label}>STANDARD MONTHLY WORKING DAYS</Text>
                <TextInput
                  style={styles.input}
                  value={standardWorkingDays}
                  onChangeText={setStandardWorkingDays}
                  keyboardType="numeric"
                />
              </View>

              <View style={styles.settingRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.settingRowTitle}>Auto Tax & PF Deduction</Text>
                  <Text style={styles.settingRowSub}>Calculate statutory deductions on gross salary</Text>
                </View>
                <Switch
                  value={autoTax}
                  onValueChange={setAutoTax}
                  trackColor={{ false: "#CBD5E1", true: "#93C5FD" }}
                  thumbColor={autoTax ? "#0B2253" : "#F1F5F9"}
                />
              </View>

              <View style={styles.settingRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.settingRowTitle}>Auto Email PDF Payslips</Text>
                  <Text style={styles.settingRowSub}>Email generated payslips directly to staff</Text>
                </View>
                <Switch
                  value={autoEmailPayslip}
                  onValueChange={setAutoEmailPayslip}
                  trackColor={{ false: "#CBD5E1", true: "#93C5FD" }}
                  thumbColor={autoEmailPayslip ? "#0B2253" : "#F1F5F9"}
                />
              </View>

              <TouchableOpacity
                style={styles.saveButton}
                activeOpacity={0.8}
                onPress={() => handleSave("Payroll Rules")}
              >
                <Ionicons name="checkmark-circle-outline" size={18} color="#FFF" />
                <Text style={styles.saveButtonText}>Save Payroll Rules</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* TAB 7: ADMIN PROFILE */}
          {activeTab === "profile" && (
            <>
              {/* Profile Top Banner Card */}
              <View style={styles.profileCard}>
                <LinearGradient
                  colors={["#0F2460", "#0B2253"]}
                  style={styles.profileHeaderBanner}
                >
                  <View style={styles.avatarLarge}>
                    <Ionicons name="shield-checkmark-sharp" size={44} color="#FFF" />
                  </View>
                </LinearGradient>

                <View style={styles.profileBody}>
                  <Text style={styles.profileName}>{profileUsername || "..."}</Text>
                  <Text style={styles.profileEmail}>{profileEmail || "No email set"}</Text>

                  <View style={styles.roleBadgeRow}>
                    <View style={styles.roleBadge}>
                      <Ionicons name="star" size={12} color="#0B2253" />
                      <Text style={styles.roleText}>{profileRole === "hr" ? "HR" : profileRole.toUpperCase()}</Text>
                    </View>
                    <View style={styles.verifiedBadge}>
                      <Ionicons name="checkmark-circle" size={12} color="#10B981" />
                      <Text style={styles.verifiedText}>ACTIVE</Text>
                    </View>
                  </View>

                  {!!profileCreatedAt && (
                    <View style={styles.statsRow}>
                      <View style={styles.statItem}>
                        <Text style={styles.statVal}>{profileCreatedAt.split(" ")[0]}</Text>
                        <Text style={styles.statLbl}>Account Created</Text>
                      </View>
                    </View>
                  )}
                </View>
              </View>

              {/* Admin Actions */}
              <View style={styles.card}>
                <Text style={[styles.cardHeaderTitle, { marginBottom: 14 }]}>Account Management & Actions</Text>

                <TouchableOpacity
                  style={styles.actionRow}
                  activeOpacity={0.7}
                  onPress={() => setActiveTab("security")}
                >
                  <View style={styles.actionIconBox}>
                    <Ionicons name="key-outline" size={20} color="#0B2253" />
                  </View>
                  <View style={{ flex: 1, marginLeft: 12 }}>
                    <Text style={styles.actionTitle}>Change Password</Text>
                    <Text style={styles.actionSub}>Update system access password</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={18} color="#94A3B8" />
                </TouchableOpacity>

                <TouchableOpacity
                  style={styles.actionRow}
                  activeOpacity={0.7}
                  onPress={() => setActiveTab("company")}
                >
                  <View style={styles.actionIconBox}>
                    <Ionicons name="business-outline" size={20} color="#0B2253" />
                  </View>
                  <View style={{ flex: 1, marginLeft: 12 }}>
                    <Text style={styles.actionTitle}>Organization Info</Text>
                    <Text style={styles.actionSub}>Manage company profile & details</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={18} color="#94A3B8" />
                </TouchableOpacity>

                <TouchableOpacity
                  style={styles.actionRow}
                  activeOpacity={0.7}
                  onPress={() => setActiveTab("notifications")}
                >
                  <View style={styles.actionIconBox}>
                    <Ionicons name="notifications-outline" size={20} color="#0B2253" />
                  </View>
                  <View style={{ flex: 1, marginLeft: 12 }}>
                    <Text style={styles.actionTitle}>Alert Preferences</Text>
                    <Text style={styles.actionSub}>Manage system notifications</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={18} color="#94A3B8" />
                </TouchableOpacity>

                <TouchableOpacity
                  style={styles.logoutBtn}
                  activeOpacity={0.8}
                  onPress={signOut}
                >
                  <Ionicons name="log-out-outline" size={18} color="#EF4444" />
                  <Text style={styles.logoutBtnText}>Sign Out of Admin Portal</Text>
                </TouchableOpacity>
              </View>
            </>
          )}

          <View style={{ height: 110 }} />
        </ScrollView>

        {/* Modal: Add Shift */}
        <Modal
          visible={addShiftModal}
          transparent
          animationType="slide"
          onRequestClose={() => setAddShiftModal(false)}
        >
          <View style={styles.modalOverlay}>
            <View style={styles.modalCard}>
              <View style={styles.modalHeader}>
                <Text style={styles.modalTitle}>Create New Work Shift</Text>
                <TouchableOpacity onPress={() => setAddShiftModal(false)}>
                  <Ionicons name="close" size={22} color="#64748B" />
                </TouchableOpacity>
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.label}>SHIFT NAME</Text>
                <TextInput
                  style={styles.input}
                  placeholder="e.g. Night Shift B"
                  value={newShiftName}
                  onChangeText={setNewShiftName}
                />
              </View>

              <View style={styles.twoCol}>
                <View style={[styles.inputGroup, { flex: 1, marginRight: 8 }]}>
                  <Text style={styles.label}>START TIME</Text>
                  <TextInput
                    style={styles.input}
                    value={newShiftStart}
                    onChangeText={setNewShiftStart}
                  />
                </View>
                <View style={[styles.inputGroup, { flex: 1, marginLeft: 8 }]}>
                  <Text style={styles.label}>END TIME</Text>
                  <TextInput
                    style={styles.input}
                    value={newShiftEnd}
                    onChangeText={setNewShiftEnd}
                  />
                </View>
              </View>

              <TouchableOpacity
                style={styles.saveButton}
                activeOpacity={0.8}
                onPress={handleAddShift}
              >
                <Text style={styles.saveButtonText}>Add Shift</Text>
              </TouchableOpacity>
            </View>
          </View>
        </Modal>
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },

  // Horizontal Tab Bar
  tabBarContainer: {
    backgroundColor: "#FFFFFF",
    borderBottomWidth: 1,
    borderBottomColor: "#E2E8F0",
    paddingVertical: 10,
    elevation: 2,
  },
  tabBarContent: {
    paddingHorizontal: 16,
    flexDirection: "row",
    alignItems: "center",
  },
  tabButton: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: "#F1F5F9",
    marginRight: 8,
  },
  tabButtonActive: {
    backgroundColor: "#0B2253",
  },
  tabText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#64748B",
    marginLeft: 6,
  },
  tabTextActive: {
    color: "#FFFFFF",
  },

  content: {
    paddingHorizontal: 18,
    paddingTop: 16,
  },

  // Base Card
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 22,
    padding: 20,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    elevation: 3,
    shadowColor: "#0F172A",
    shadowOpacity: 0.06,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
  },
  cardHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 18,
  },
  cardHeaderBetween: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 18,
  },
  cardHeaderTitle: {
    fontSize: 15,
    fontWeight: "800",
    color: "#0F172A",
    marginLeft: 8,
  },

  // Form Inputs
  inputGroup: {
    marginBottom: 14,
  },
  label: {
    fontSize: 11,
    fontWeight: "800",
    color: "#64748B",
    letterSpacing: 0.6,
    marginBottom: 6,
  },
  input: {
    backgroundColor: "#F8FAFC",
    borderWidth: 1.5,
    borderColor: "#E2E8F0",
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 13,
    fontWeight: "600",
    color: "#0F172A",
  },
  twoCol: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  daysToggleRow: {
    flexDirection: "row",
    gap: 8,
  },
  chipBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 10,
    backgroundColor: "#F1F5F9",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#CBD5E1",
  },
  chipBtnActive: {
    backgroundColor: "#0B2253",
    borderColor: "#0B2253",
  },
  chipText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#475569",
  },
  chipTextActive: {
    color: "#FFFFFF",
  },

  // Buttons
  saveButton: {
    backgroundColor: "#0B2253",
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    paddingVertical: 14,
    borderRadius: 14,
    marginTop: 10,
    elevation: 3,
  },
  saveButtonText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "800",
    marginLeft: 8,
  },

  // Setting Rows with Switch
  settingRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#F1F5F9",
  },
  settingRowTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#0F172A",
  },
  settingRowSub: {
    fontSize: 12,
    color: "#64748B",
    marginTop: 2,
  },
  divider: {
    height: 1,
    backgroundColor: "#E2E8F0",
    marginVertical: 14,
  },

  // Shifts Tab Specifics
  smallAddBtn: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#EEF4FF",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
  },
  smallAddBtnText: {
    color: "#0B2253",
    fontSize: 12,
    fontWeight: "700",
    marginLeft: 4,
  },
  shiftCardItem: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    borderRadius: 14,
    padding: 12,
    marginBottom: 10,
  },
  shiftIconBox: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: "#EEF4FF",
    justifyContent: "center",
    alignItems: "center",
  },
  shiftName: {
    fontSize: 13,
    fontWeight: "700",
    color: "#0F172A",
  },
  shiftTiming: {
    fontSize: 12,
    color: "#64748B",
    marginTop: 2,
  },
  activeTag: {
    backgroundColor: "#DCFCE7",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 10,
  },
  activeTagText: {
    color: "#15803D",
    fontSize: 11,
    fontWeight: "700",
  },

  // Security Box
  securityStatusBox: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#ECFDF5",
    borderWidth: 1,
    borderColor: "#A7F3D0",
    borderRadius: 16,
    padding: 14,
    marginBottom: 16,
  },
  securityStatusIcon: {
    width: 44,
    height: 44,
    borderRadius: 14,
    backgroundColor: "#D1FAE5",
    justifyContent: "center",
    alignItems: "center",
  },
  securityStatusTitle: {
    fontSize: 13,
    fontWeight: "800",
    color: "#065F46",
  },
  securityStatusSub: {
    fontSize: 12,
    color: "#047857",
    marginTop: 2,
  },

  // Admin Profile Tab
  profileCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 24,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    overflow: "hidden",
    elevation: 3,
  },
  profileHeaderBanner: {
    height: 100,
    justifyContent: "flex-end",
    alignItems: "center",
    paddingBottom: 0,
  },
  avatarLarge: {
    width: 76,
    height: 76,
    borderRadius: 38,
    backgroundColor: "#0B2253",
    borderWidth: 4,
    borderColor: "#FFFFFF",
    justifyContent: "center",
    alignItems: "center",
    marginBottom: -38,
    elevation: 4,
  },
  profileBody: {
    paddingTop: 46,
    paddingBottom: 20,
    paddingHorizontal: 20,
    alignItems: "center",
  },
  profileName: {
    fontSize: 18,
    fontWeight: "800",
    color: "#0F172A",
  },
  profileEmail: {
    fontSize: 13,
    color: "#64748B",
    marginTop: 2,
  },
  roleBadgeRow: {
    flexDirection: "row",
    gap: 8,
    marginTop: 12,
  },
  roleBadge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#EEF4FF",
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 14,
  },
  roleText: {
    color: "#0B2253",
    fontSize: 11,
    fontWeight: "800",
    marginLeft: 4,
  },
  verifiedBadge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#ECFDF5",
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 14,
  },
  verifiedText: {
    color: "#065F46",
    fontSize: 11,
    fontWeight: "800",
    marginLeft: 4,
  },
  statsRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    borderRadius: 16,
    paddingVertical: 12,
    paddingHorizontal: 16,
    marginTop: 16,
    width: "100%",
  },
  statItem: {
    flex: 1,
    alignItems: "center",
  },
  statVal: {
    fontSize: 15,
    fontWeight: "800",
    color: "#0B2253",
  },
  statLbl: {
    fontSize: 11,
    color: "#64748B",
    marginTop: 2,
  },
  statSep: {
    width: 1,
    height: 24,
    backgroundColor: "#CBD5E1",
  },
  actionRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: "#F1F5F9",
  },
  actionIconBox: {
    width: 38,
    height: 38,
    borderRadius: 12,
    backgroundColor: "#EEF4FF",
    justifyContent: "center",
    alignItems: "center",
  },
  actionTitle: {
    fontSize: 14,
    fontWeight: "700",
    color: "#0F172A",
  },
  actionSub: {
    fontSize: 12,
    color: "#64748B",
    marginTop: 2,
  },
  logoutBtn: {
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#FEF2F2",
    borderWidth: 1,
    borderColor: "#FECACA",
    paddingVertical: 14,
    borderRadius: 14,
    marginTop: 16,
  },
  logoutBtnText: {
    color: "#EF4444",
    fontSize: 14,
    fontWeight: "800",
    marginLeft: 8,
  },

  // Modal
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.5)",
    justifyContent: "center",
    paddingHorizontal: 20,
  },
  modalCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 22,
    padding: 20,
    elevation: 10,
  },
  modalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 16,
  },
  modalTitle: {
    fontSize: 17,
    fontWeight: "800",
    color: "#0F172A",
  },
});