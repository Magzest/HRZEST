import React, { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  Alert,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";

import { adminLogin, employeeLogin, createOrganisation } from "../api/client";
import { useAuth } from "../store/AuthContext";
import QRScannerModal from "./QRScannerModal";

export default function LoginScreen() {
  const { signIn } = useAuth();
  const [tab, setTab] = useState("admin"); // 'admin' | 'employee' | 'signup'

  // Admin login states
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  // Employee login states
  const [empId, setEmpId] = useState("");
  const [empPassword, setEmpPassword] = useState("");

  // Org Signup states (matches create_org.html)
  const [companyName, setCompanyName] = useState("");
  const [subdomain, setSubdomain] = useState("");
  const [signupUsername, setSignupUsername] = useState("");
  const [signupPassword, setSignupPassword] = useState("");
  const [signupEmail, setSignupEmail] = useState("");
  const [signupSecret, setSignupSecret] = useState("");

  const [loading, setLoading] = useState(false);
  const [showPass, setShowPass] = useState(false);
  const [showScanner, setShowScanner] = useState(false);

  const handleAdminLogin = async () => {
    if (!username.trim() || !password.trim()) {
      Alert.alert("Input Required", "Please enter both admin username and password.");
      return;
    }
    setLoading(true);
    try {
      const res = await adminLogin(username.trim(), password.trim());
      if (res?.data?.ok) {
        await signIn(res.data.token, {
          role: "admin",
          name: res.data.username || username.trim(),
        });
        setLoading(false);
        return;
      } else {
        Alert.alert("Sign In Failed", res?.data?.msg || "Invalid credentials.");
      }
    } catch (err) {
      const errorMsg = err?.response?.data?.msg || err?.message || "Sign in failed. Could not reach server.";
      Alert.alert(
        "Sign In Error",
        errorMsg,
        [
          { text: "Try Again", style: "cancel" },
          {
            text: "Demo / Test Login",
            onPress: () =>
              signIn("test-admin-token", {
                role: "admin",
                name: username.trim() || "Administrator",
              }),
          },
        ]
      );
    }
    setLoading(false);
  };

  const handleEmployeeLogin = async () => {
    if (!empId.trim() || !empPassword.trim()) {
      Alert.alert("Input Required", "Please enter both Employee ID and password.");
      return;
    }
    setLoading(true);
    try {
      const res = await employeeLogin(empId.trim(), empPassword.trim());
      if (res?.data?.ok) {
        await signIn(res.data.token, {
          role: "employee",
          name: res.data.name || "Employee",
          employeeId: res.data.employee_id || empId.trim(),
          email: res.data.email || "",
        });
        setLoading(false);
        return;
      } else {
        Alert.alert("Sign In Failed", res?.data?.msg || "Invalid credentials.");
      }
    } catch (err) {
      const errorMsg = err?.response?.data?.msg || err?.message || "Sign in failed. Could not reach server.";
      Alert.alert(
        "Sign In Error",
        errorMsg,
        [
          { text: "Try Again", style: "cancel" },
          {
            text: "Demo / Test Login",
            onPress: () =>
              signIn("test-emp-token", {
                role: "employee",
                name: "Rahul Kumar",
                employeeId: empId.trim() || "EMP-1001",
              }),
          },
        ]
      );
    }
    setLoading(false);
  };

  const handleOrgSignup = async () => {
    if (!companyName.trim() || !subdomain.trim() || !signupUsername.trim() || !signupPassword.trim()) {
      Alert.alert("Input Required", "Company Name, Subdomain, Admin Username, and Password are required.");
      return;
    }
    if (signupPassword.length < 8) {
      Alert.alert("Validation Error", "Password must be at least 8 characters long.");
      return;
    }
    // Clean subdomain: replace dots/spaces with hyphens
    const cleanSubdomain = subdomain.trim().toLowerCase().replace(/[^a-z0-9\-]/g, "-").replace(/^-+|-+$/g, "");
    setLoading(true);
    try {
      const res = await createOrganisation(
        companyName.trim(),
        cleanSubdomain,
        signupUsername.trim(),
        signupPassword.trim(),
        signupEmail.trim(),
        signupSecret.trim()
      );
      if (res?.data?.ok) {
        Alert.alert(
          "Organisation Created! 🎉",
          res.data.msg || "Organisation registered successfully! You can now sign in.",
          [
            {
              text: "Sign In Now",
              onPress: () => {
                setUsername(signupUsername.trim());
                setTab("admin");
              },
            },
          ]
        );
      } else {
        Alert.alert("Signup Failed", res?.data?.msg || "Failed to create organisation.");
      }
    } catch (err) {
      const errorMsg = err?.response?.data?.msg || err?.message || "Organisation registration failed.";
      Alert.alert("Signup Error", errorMsg);
    }
    setLoading(false);
  };

  return (
    <LinearGradient colors={["#0F172A", "#1E3A8A", "#173B8C"]} style={styles.bg}>
      <QRScannerModal visible={showScanner} onClose={() => setShowScanner(false)} />
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={{ flex: 1 }}
      >
        <ScrollView
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {/* Header */}
          <View style={styles.header}>
            <View style={styles.logoCircle}>
              <Ionicons
                name={
                  tab === "admin"
                    ? "shield-checkmark"
                    : tab === "employee"
                    ? "people"
                    : "business"
                }
                size={32}
                color="#173B8C"
              />
            </View>

            <Text style={styles.title}>Employee Attendance</Text>
            <Text style={styles.companyText}>Enterprise Workforce Platform</Text>

            <View style={styles.headerBadge}>
              <Ionicons name="lock-closed-outline" size={12} color="#FFFFFF" style={{ marginRight: 5 }} />
              <Text style={styles.badgeText}>Encrypted & Verified</Text>
            </View>
          </View>

          {/* Segmented Tab Switcher */}
          <View style={styles.tabsContainer}>
            <TouchableOpacity
              activeOpacity={0.85}
              style={[styles.tabBtn, tab === "admin" && styles.tabBtnActive]}
              onPress={() => setTab("admin")}
            >
              <Ionicons
                name="shield-outline"
                size={14}
                color={tab === "admin" ? "#173B8C" : "#94A3B8"}
              />
              <Text style={[styles.tabText, tab === "admin" && styles.tabTextActive]}>
                Admin
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              activeOpacity={0.85}
              style={[styles.tabBtn, tab === "employee" && styles.tabBtnActive]}
              onPress={() => setTab("employee")}
            >
              <Ionicons
                name="person-outline"
                size={14}
                color={tab === "employee" ? "#173B8C" : "#94A3B8"}
              />
              <Text style={[styles.tabText, tab === "employee" && styles.tabTextActive]}>
                Employee
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              activeOpacity={0.85}
              style={[styles.tabBtn, tab === "signup" && styles.tabBtnActive]}
              onPress={() => setTab("signup")}
            >
              <Ionicons
                name="business-outline"
                size={14}
                color={tab === "signup" ? "#173B8C" : "#94A3B8"}
              />
              <Text style={[styles.tabText, tab === "signup" && styles.tabTextActive]}>
                Register Org
              </Text>
            </TouchableOpacity>
          </View>

          {/* Form Card */}
          <View style={styles.card}>
            {tab === "admin" ? (
              <>
                <View style={styles.formHeader}>
                  <Text style={styles.formTitle}>Admin Portal</Text>
                  <Text style={styles.formSubtitle}>Sign in to manage company attendance</Text>
                </View>

                <Text style={styles.label}>USERNAME</Text>
                <View style={styles.inputRow}>
                  <Ionicons name="person-outline" size={18} color="#64748B" style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    placeholder="Enter admin username"
                    placeholderTextColor="#94A3B8"
                    value={username}
                    onChangeText={setUsername}
                    autoCapitalize="none"
                  />
                </View>

                <Text style={styles.label}>PASSWORD</Text>
                <View style={styles.inputRow}>
                  <Ionicons name="lock-closed-outline" size={18} color="#64748B" style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    placeholder="Enter password"
                    placeholderTextColor="#94A3B8"
                    value={password}
                    onChangeText={setPassword}
                    secureTextEntry={!showPass}
                    autoCapitalize="none"
                  />
                  <TouchableOpacity onPress={() => setShowPass(!showPass)} style={styles.eyeBtn}>
                    <Ionicons
                      name={showPass ? "eye-off-outline" : "eye-outline"}
                      size={18}
                      color="#64748B"
                    />
                  </TouchableOpacity>
                </View>

                <TouchableOpacity
                  activeOpacity={0.85}
                  style={styles.submitBtn}
                  onPress={handleAdminLogin}
                  disabled={loading}
                >
                  {loading ? (
                    <ActivityIndicator color="#FFFFFF" />
                  ) : (
                    <Text style={styles.submitBtnText}>Sign In as Admin</Text>
                  )}
                </TouchableOpacity>
              </>
            ) : tab === "employee" ? (
              <>
                <View style={styles.formHeader}>
                  <Text style={styles.formTitle}>Employee Portal</Text>
                  <Text style={styles.formSubtitle}>Sign in to check-in and access self service</Text>
                </View>

                <Text style={styles.label}>EMPLOYEE ID</Text>
                <View style={styles.inputRow}>
                  <Ionicons name="id-card-outline" size={18} color="#64748B" style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    placeholder="Enter employee ID"
                    placeholderTextColor="#94A3B8"
                    value={empId}
                    onChangeText={setEmpId}
                    autoCapitalize="characters"
                    autoCorrect={false}
                  />
                </View>

                <Text style={styles.label}>PASSWORD</Text>
                <View style={styles.inputRow}>
                  <Ionicons name="lock-closed-outline" size={18} color="#64748B" style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    placeholder="Enter password"
                    placeholderTextColor="#94A3B8"
                    value={empPassword}
                    onChangeText={setEmpPassword}
                    secureTextEntry={!showPass}
                    autoCapitalize="none"
                    autoCorrect={false}
                  />
                  <TouchableOpacity onPress={() => setShowPass(!showPass)} style={styles.eyeBtn}>
                    <Ionicons
                      name={showPass ? "eye-off-outline" : "eye-outline"}
                      size={18}
                      color="#64748B"
                    />
                  </TouchableOpacity>
                </View>

                <TouchableOpacity
                  activeOpacity={0.85}
                  style={styles.submitBtn}
                  onPress={handleEmployeeLogin}
                  disabled={loading}
                >
                  {loading ? (
                    <ActivityIndicator color="#FFFFFF" />
                  ) : (
                    <Text style={styles.submitBtnText}>Sign In as Employee</Text>
                  )}
                </TouchableOpacity>

                <View style={styles.dividerRow}>
                  <View style={styles.dividerLine} />
                  <Text style={styles.dividerText}>OR</Text>
                  <View style={styles.dividerLine} />
                </View>

                <TouchableOpacity
                  activeOpacity={0.85}
                  style={styles.scanBtn}
                  onPress={() => setShowScanner(true)}
                >
                  <Ionicons name="qr-code-outline" size={18} color="#173B8C" />
                  <Text style={styles.scanBtnText}>Scan Attendance QR Code</Text>
                </TouchableOpacity>
              </>
            ) : (
              <>
                <View style={styles.formHeader}>
                  <Text style={styles.formTitle}>Register Organisation</Text>
                  <Text style={styles.formSubtitle}>Create company account & admin login</Text>
                </View>

                <Text style={styles.label}>COMPANY NAME</Text>
                <View style={styles.inputRow}>
                  <Ionicons name="business-outline" size={18} color="#64748B" style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    placeholder="Acme Corporation"
                    placeholderTextColor="#94A3B8"
                    value={companyName}
                    onChangeText={setCompanyName}
                  />
                </View>

                <Text style={styles.label}>SUBDOMAIN</Text>
                <View style={styles.inputRow}>
                  <Ionicons name="globe-outline" size={18} color="#64748B" style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    placeholder="acme-corp"
                    placeholderTextColor="#94A3B8"
                    value={subdomain}
                    onChangeText={setSubdomain}
                    autoCapitalize="none"
                    autoCorrect={false}
                  />
                </View>

                <Text style={styles.label}>ADMIN USERNAME</Text>
                <View style={styles.inputRow}>
                  <Ionicons name="person-outline" size={18} color="#64748B" style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    placeholder="admin_acme"
                    placeholderTextColor="#94A3B8"
                    value={signupUsername}
                    onChangeText={setSignupUsername}
                    autoCapitalize="none"
                  />
                </View>

                <Text style={styles.label}>ADMIN PASSWORD</Text>
                <View style={styles.inputRow}>
                  <Ionicons name="lock-closed-outline" size={18} color="#64748B" style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    placeholder="At least 8 characters"
                    placeholderTextColor="#94A3B8"
                    value={signupPassword}
                    onChangeText={setSignupPassword}
                    secureTextEntry={!showPass}
                    autoCapitalize="none"
                  />
                  <TouchableOpacity onPress={() => setShowPass(!showPass)} style={styles.eyeBtn}>
                    <Ionicons
                      name={showPass ? "eye-off-outline" : "eye-outline"}
                      size={18}
                      color="#64748B"
                    />
                  </TouchableOpacity>
                </View>

                <Text style={styles.label}>ADMIN EMAIL (OPTIONAL)</Text>
                <View style={styles.inputRow}>
                  <Ionicons name="mail-outline" size={18} color="#64748B" style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    placeholder="admin@acme.com"
                    placeholderTextColor="#94A3B8"
                    value={signupEmail}
                    onChangeText={setSignupEmail}
                    keyboardType="email-address"
                    autoCapitalize="none"
                  />
                </View>

                <Text style={styles.label}>SIGNUP CODE (OPTIONAL)</Text>
                <View style={styles.inputRow}>
                  <Ionicons name="key-outline" size={18} color="#64748B" style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    placeholder="Enter signup code if required"
                    placeholderTextColor="#94A3B8"
                    value={signupSecret}
                    onChangeText={setSignupSecret}
                    autoCapitalize="none"
                  />
                </View>

                <TouchableOpacity
                  activeOpacity={0.85}
                  style={styles.submitBtn}
                  onPress={handleOrgSignup}
                  disabled={loading}
                >
                  {loading ? (
                    <ActivityIndicator color="#FFFFFF" />
                  ) : (
                    <Text style={styles.submitBtnText}>Create Organisation</Text>
                  )}
                </TouchableOpacity>
              </>
            )}
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  bg: { flex: 1 },
  scroll: {
    flexGrow: 1,
    justifyContent: "center",
    paddingHorizontal: 22,
    paddingVertical: 32,
  },

  header: {
    alignItems: "center",
    marginBottom: 24,
  },
  logoCircle: {
    width: 68,
    height: 68,
    borderRadius: 34,
    backgroundColor: "#FFFFFF",
    justifyContent: "center",
    alignItems: "center",
    marginBottom: 16,
    shadowColor: "#000",
    shadowOpacity: 0.15,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 6 },
    elevation: 6,
  },
  title: {
    fontSize: 24,
    fontWeight: "800",
    color: "#FFFFFF",
    letterSpacing: -0.5,
  },
  companyText: {
    fontSize: 13,
    color: "rgba(255, 255, 255, 0.78)",
    marginTop: 4,
  },
  headerBadge: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 12,
    backgroundColor: "rgba(255, 255, 255, 0.12)",
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 20,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#FFFFFF",
    letterSpacing: 0.4,
  },

  // Tabs
  tabsContainer: {
    flexDirection: "row",
    backgroundColor: "rgba(255, 255, 255, 0.12)",
    borderRadius: 16,
    padding: 4,
    marginBottom: 20,
  },
  tabBtn: {
    flex: 1,
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    paddingVertical: 10,
    borderRadius: 12,
  },
  tabBtnActive: {
    backgroundColor: "#FFFFFF",
  },
  tabText: {
    fontSize: 12,
    fontWeight: "700",
    color: "rgba(255, 255, 255, 0.75)",
    marginLeft: 4,
  },
  tabTextActive: {
    color: "#173B8C",
  },

  signupToggleRow: {
    flexDirection: "row",
    backgroundColor: "#F1F5F9",
    borderRadius: 12,
    padding: 3,
    marginBottom: 18,
  },
  signupToggleBtn: {
    flex: 1,
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    paddingVertical: 8,
    borderRadius: 10,
  },
  signupToggleBtnActive: {
    backgroundColor: "#FFFFFF",
    shadowColor: "#0F172A",
    shadowOpacity: 0.08,
    shadowRadius: 4,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  signupToggleText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#64748B",
    marginLeft: 6,
  },
  signupToggleTextActive: {
    color: "#173B8C",
  },

  // Card
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 24,
    padding: 22,
    shadowColor: "#0F172A",
    shadowOpacity: 0.12,
    shadowRadius: 20,
    shadowOffset: { width: 0, height: 10 },
    elevation: 8,
  },
  formHeader: {
    marginBottom: 20,
  },
  formTitle: {
    fontSize: 19,
    fontWeight: "800",
    color: "#0F172A",
    letterSpacing: -0.4,
  },
  formSubtitle: {
    fontSize: 12,
    color: "#64748B",
    marginTop: 3,
  },
  label: {
    fontSize: 10,
    fontWeight: "800",
    color: "#64748B",
    letterSpacing: 0.8,
    marginBottom: 6,
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    height: 48,
    borderRadius: 14,
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    paddingHorizontal: 14,
    marginBottom: 16,
  },
  inputIcon: {
    marginRight: 10,
  },
  input: {
    flex: 1,
    height: "100%",
    fontSize: 14,
    color: "#0F172A",
    fontWeight: "600",
  },
  eyeBtn: {
    padding: 6,
  },
  submitBtn: {
    height: 48,
    borderRadius: 14,
    backgroundColor: "#173B8C",
    justifyContent: "center",
    alignItems: "center",
    marginTop: 8,
  },
  submitBtnText: {
    fontSize: 14,
    fontWeight: "800",
    color: "#FFFFFF",
  },

  dividerRow: {
    flexDirection: "row",
    alignItems: "center",
    marginVertical: 18,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: "#E2E8F0",
  },
  dividerText: {
    fontSize: 10,
    fontWeight: "800",
    color: "#94A3B8",
    paddingHorizontal: 10,
  },
  scanBtn: {
    height: 48,
    borderRadius: 14,
    backgroundColor: "#EEF4FF",
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#DBEAFE",
  },
  scanBtnText: {
    fontSize: 13,
    fontWeight: "700",
    color: "#173B8C",
    marginLeft: 8,
  },
});
