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
} from "react-native";
import { DrawerActions } from "@react-navigation/native";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";

import AdminHeader from "../../components/admin/AdminHeader";
import THEME from "../../constants/theme";
import { useAuth } from "../../store/AuthContext";

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

  // Form States - Company
  const [companyName, setCompanyName] = useState("HR Management System Inc.");
  const [companyCode, setCompanyCode] = useState("HRMS-PRO-2026");
  const [companyEmail, setCompanyEmail] = useState("support@company.com");
  const [companyPhone, setCompanyPhone] = useState("+1 (555) 019-2834");
  const [companyAddress, setCompanyAddress] = useState("123 Corporate Blvd, Suite 400");
  const [workingDays, setWorkingDays] = useState("Mon - Fri");

  // Form States - Shifts
  const [shifts, setShifts] = useState([
    { id: 1, name: "General Shift", start: "09:00 AM", end: "06:00 PM", half: "01:00 PM" },
    { id: 2, name: "Morning Shift", start: "07:00 AM", end: "04:00 PM", half: "11:30 AM" },
    { id: 3, name: "Evening Shift", start: "02:00 PM", end: "11:00 PM", half: "06:30 PM" },
  ]);
  const [gracePeriod, setGracePeriod] = useState("15");
  const [halfDayHours, setHalfDayHours] = useState("4.0");

  // Form States - Attendance & Geofence
  const [geofenceEnabled, setGeofenceEnabled] = useState(true);
  const [geofenceRadius, setGeofenceRadius] = useState("200");
  const [latitude, setLatitude] = useState("17.3850");
  const [longitude, setLongitude] = useState("78.4867");
  const [faceRecog, setFaceRecog] = useState(true);
  const [livenessCheck, setLivenessCheck] = useState(true);
  const [autoCheckout, setAutoCheckout] = useState(true);

  // Form States - Security
  const [twoFactorActive, setTwoFactorActive] = useState(true);
  const [sessionTimeout, setSessionTimeout] = useState("30");
  const [ipWhitelist, setIpWhitelist] = useState(false);
  const [currentPass, setCurrentPass] = useState("");
  const [newPass, setNewPass] = useState("");
  const [confirmPass, setConfirmPass] = useState("");

  // Form States - Notifications
  const [pushNotifs, setPushNotifs] = useState(true);
  const [emailAlerts, setEmailAlerts] = useState(true);
  const [dailyDigest, setDailyDigest] = useState(true);
  const [lateAlerts, setLateAlerts] = useState(true);
  const [payslipAlerts, setPayslipAlerts] = useState(true);

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

  const handleSave = (sectionName) => {
    Alert.alert("Success", `${sectionName} settings updated successfully!`);
  };

  const handleChangePassword = () => {
    if (!currentPass || !newPass || !confirmPass) {
      Alert.alert("Validation Error", "Please fill in all password fields.");
      return;
    }
    if (newPass !== confirmPass) {
      Alert.alert("Error", "New password and confirmation do not match.");
      return;
    }
    Alert.alert("Success", "Admin password changed successfully.");
    setCurrentPass("");
    setNewPass("");
    setConfirmPass("");
  };

  const handleAddShift = () => {
    if (!newShiftName.trim()) {
      Alert.alert("Error", "Please enter shift name.");
      return;
    }
    const newId = Date.now();
    setShifts([...shifts, { id: newId, name: newShiftName, start: newShiftStart, end: newShiftEnd, half: "01:00 PM" }]);
    setAddShiftModal(false);
    setNewShiftName("");
    Alert.alert("Success", `Shift "${newShiftName}" created successfully!`);
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
                <Ionicons name="business" size={22} color="#173B8C" />
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

              <View style={styles.twoCol}>
                <View style={[styles.inputGroup, { flex: 1, marginRight: 8 }]}>
                  <Text style={styles.label}>SUPPORT EMAIL</Text>
                  <TextInput
                    style={styles.input}
                    value={companyEmail}
                    onChangeText={setCompanyEmail}
                    keyboardType="email-address"
                  />
                </View>
                <View style={[styles.inputGroup, { flex: 1, marginLeft: 8 }]}>
                  <Text style={styles.label}>SUPPORT PHONE</Text>
                  <TextInput
                    style={styles.input}
                    value={companyPhone}
                    onChangeText={setCompanyPhone}
                    keyboardType="phone-pad"
                  />
                </View>
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.label}>HEADQUARTERS ADDRESS</Text>
                <TextInput
                  style={[styles.input, { height: 70 }]}
                  multiline
                  value={companyAddress}
                  onChangeText={setCompanyAddress}
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
                onPress={() => handleSave("Company")}
              >
                <Ionicons name="checkmark-circle-outline" size={18} color="#FFF" />
                <Text style={styles.saveButtonText}>Save Profile Settings</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* TAB 2: SHIFTS & TIMINGS */}
          {activeTab === "shifts" && (
            <View style={styles.card}>
              <View style={styles.cardHeaderBetween}>
                <View style={{ flexDirection: "row", alignItems: "center" }}>
                  <Ionicons name="time" size={22} color="#173B8C" />
                  <Text style={[styles.cardHeaderTitle, { marginLeft: 8 }]}>Work Shifts & Grace Timings</Text>
                </View>
                <TouchableOpacity
                  style={styles.smallAddBtn}
                  onPress={() => setAddShiftModal(true)}
                >
                  <Ionicons name="add-circle" size={16} color="#173B8C" />
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
                    <Ionicons name="alarm-outline" size={20} color="#173B8C" />
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
                <Ionicons name="location" size={22} color="#173B8C" />
                <Text style={styles.cardHeaderTitle}>GPS Geofence & Facial Verification</Text>
              </View>

              <View style={styles.settingRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.settingRowTitle}>GPS Geofence Restriction</Text>
                  <Text style={styles.settingRowSub}>Limit check-in to office GPS radius</Text>
                </View>
                <Switch
                  value={geofenceEnabled}
                  onValueChange={setGeofenceEnabled}
                  trackColor={{ false: "#CBD5E1", true: "#93C5FD" }}
                  thumbColor={geofenceEnabled ? "#173B8C" : "#F1F5F9"}
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
                  onValueChange={setFaceRecog}
                  trackColor={{ false: "#CBD5E1", true: "#93C5FD" }}
                  thumbColor={faceRecog ? "#173B8C" : "#F1F5F9"}
                />
              </View>

              <View style={styles.settingRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.settingRowTitle}>Liveness Detection</Text>
                  <Text style={styles.settingRowSub}>Prevent spoofing using printed photos</Text>
                </View>
                <Switch
                  value={livenessCheck}
                  onValueChange={setLivenessCheck}
                  trackColor={{ false: "#CBD5E1", true: "#93C5FD" }}
                  thumbColor={livenessCheck ? "#173B8C" : "#F1F5F9"}
                />
              </View>

              <View style={styles.settingRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.settingRowTitle}>Auto Check-out (08:00 PM)</Text>
                  <Text style={styles.settingRowSub}>Automatically check out unclosed sessions</Text>
                </View>
                <Switch
                  value={autoCheckout}
                  onValueChange={setAutoCheckout}
                  trackColor={{ false: "#CBD5E1", true: "#93C5FD" }}
                  thumbColor={autoCheckout ? "#173B8C" : "#F1F5F9"}
                />
              </View>

              <TouchableOpacity
                style={styles.saveButton}
                activeOpacity={0.8}
                onPress={() => handleSave("Attendance")}
              >
                <Ionicons name="checkmark-circle-outline" size={18} color="#FFF" />
                <Text style={styles.saveButtonText}>Save Attendance Rules</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* TAB 4: SECURITY & 2FA */}
          {activeTab === "security" && (
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <Ionicons name="shield-checkmark" size={22} color="#173B8C" />
                <Text style={styles.cardHeaderTitle}>Security & Two-Factor Authentication</Text>
              </View>

              <View style={styles.securityStatusBox}>
                <View style={styles.securityStatusIcon}>
                  <Ionicons name="shield-checkmark-sharp" size={28} color="#10B981" />
                </View>
                <View style={{ marginLeft: 14, flex: 1 }}>
                  <Text style={styles.securityStatusTitle}>Two-Factor Auth (2FA) Active</Text>
                  <Text style={styles.securityStatusSub}>System encrypted with Fernet PII tokens</Text>
                </View>
              </View>

              <View style={styles.settingRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.settingRowTitle}>Enforce 2FA for Admin Portal</Text>
                  <Text style={styles.settingRowSub}>Requires TOTP authenticator code</Text>
                </View>
                <Switch
                  value={twoFactorActive}
                  onValueChange={setTwoFactorActive}
                  trackColor={{ false: "#CBD5E1", true: "#93C5FD" }}
                  thumbColor={twoFactorActive ? "#173B8C" : "#F1F5F9"}
                />
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
              >
                <Ionicons name="key-outline" size={18} color="#FFF" />
                <Text style={styles.saveButtonText}>Update Admin Password</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* TAB 5: NOTIFICATIONS */}
          {activeTab === "notifications" && (
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <Ionicons name="notifications" size={22} color="#173B8C" />
                <Text style={styles.cardHeaderTitle}>Notification Preferences & Alerts</Text>
              </View>

              <View style={styles.settingRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.settingRowTitle}>Mobile Push Notifications</Text>
                  <Text style={styles.settingRowSub}>Immediate alerts on pending approvals</Text>
                </View>
                <Switch
                  value={pushNotifs}
                  onValueChange={setPushNotifs}
                  trackColor={{ false: "#CBD5E1", true: "#93C5FD" }}
                  thumbColor={pushNotifs ? "#173B8C" : "#F1F5F9"}
                />
              </View>

              <View style={styles.settingRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.settingRowTitle}>Security & Login Email Alerts</Text>
                  <Text style={styles.settingRowSub}>Notify on new admin sessions</Text>
                </View>
                <Switch
                  value={emailAlerts}
                  onValueChange={setEmailAlerts}
                  trackColor={{ false: "#CBD5E1", true: "#93C5FD" }}
                  thumbColor={emailAlerts ? "#173B8C" : "#F1F5F9"}
                />
              </View>

              <View style={styles.settingRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.settingRowTitle}>Daily Attendance Summary Digest</Text>
                  <Text style={styles.settingRowSub}>Receive daily PDF report at 7:00 PM</Text>
                </View>
                <Switch
                  value={dailyDigest}
                  onValueChange={setDailyDigest}
                  trackColor={{ false: "#CBD5E1", true: "#93C5FD" }}
                  thumbColor={dailyDigest ? "#173B8C" : "#F1F5F9"}
                />
              </View>

              <View style={styles.settingRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.settingRowTitle}>Late Arrival & Absentee Alerts</Text>
                  <Text style={styles.settingRowSub}>Alert HR when employees check in late</Text>
                </View>
                <Switch
                  value={lateAlerts}
                  onValueChange={setLateAlerts}
                  trackColor={{ false: "#CBD5E1", true: "#93C5FD" }}
                  thumbColor={lateAlerts ? "#173B8C" : "#F1F5F9"}
                />
              </View>

              <View style={styles.settingRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.settingRowTitle}>Payslip Issuance Notifications</Text>
                  <Text style={styles.settingRowSub}>Notify staff when payslips are published</Text>
                </View>
                <Switch
                  value={payslipAlerts}
                  onValueChange={setPayslipAlerts}
                  trackColor={{ false: "#CBD5E1", true: "#93C5FD" }}
                  thumbColor={payslipAlerts ? "#173B8C" : "#F1F5F9"}
                />
              </View>

              <TouchableOpacity
                style={styles.saveButton}
                activeOpacity={0.8}
                onPress={() => handleSave("Notifications")}
              >
                <Ionicons name="checkmark-circle-outline" size={18} color="#FFF" />
                <Text style={styles.saveButtonText}>Save Notification Settings</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* TAB 6: PAYROLL RULES */}
          {activeTab === "payroll" && (
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <Ionicons name="wallet" size={22} color="#173B8C" />
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
                  thumbColor={autoTax ? "#173B8C" : "#F1F5F9"}
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
                  thumbColor={autoEmailPayslip ? "#173B8C" : "#F1F5F9"}
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
                  colors={["#0F2460", "#173B8C"]}
                  style={styles.profileHeaderBanner}
                >
                  <View style={styles.avatarLarge}>
                    <Ionicons name="shield-checkmark-sharp" size={44} color="#FFF" />
                  </View>
                </LinearGradient>

                <View style={styles.profileBody}>
                  <Text style={styles.profileName}>Administrator</Text>
                  <Text style={styles.profileEmail}>admin@company.com</Text>

                  <View style={styles.roleBadgeRow}>
                    <View style={styles.roleBadge}>
                      <Ionicons name="star" size={12} color="#173B8C" />
                      <Text style={styles.roleText}>SUPER ADMIN</Text>
                    </View>
                    <View style={styles.verifiedBadge}>
                      <Ionicons name="checkmark-circle" size={12} color="#10B981" />
                      <Text style={styles.verifiedText}>SYSTEM ACTIVE</Text>
                    </View>
                  </View>

                  <View style={styles.statsRow}>
                    <View style={styles.statItem}>
                      <Text style={styles.statVal}>100%</Text>
                      <Text style={styles.statLbl}>Security Level</Text>
                    </View>
                    <View style={styles.statSep} />
                    <View style={styles.statItem}>
                      <Text style={styles.statVal}>2FA</Text>
                      <Text style={styles.statLbl}>Auth Status</Text>
                    </View>
                    <View style={styles.statSep} />
                    <View style={styles.statItem}>
                      <Text style={styles.statVal}>FULL</Text>
                      <Text style={styles.statLbl}>Permissions</Text>
                    </View>
                  </View>
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
                    <Ionicons name="key-outline" size={20} color="#173B8C" />
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
                    <Ionicons name="business-outline" size={20} color="#173B8C" />
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
                    <Ionicons name="notifications-outline" size={20} color="#173B8C" />
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
    backgroundColor: "#173B8C",
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
    fontSize: 17,
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
    fontSize: 14,
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
    backgroundColor: "#173B8C",
    borderColor: "#173B8C",
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
    backgroundColor: "#173B8C",
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
    fontSize: 14,
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
    fontSize: 14,
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
    color: "#173B8C",
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
    fontSize: 14,
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
    fontSize: 14,
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
    backgroundColor: "#173B8C",
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
    fontSize: 22,
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
    color: "#173B8C",
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
    color: "#173B8C",
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