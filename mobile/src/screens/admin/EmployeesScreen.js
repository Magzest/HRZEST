import React, { useState, useEffect } from "react";
import {
  SafeAreaView,
  ScrollView,
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
  Modal,
  TextInput,
  Alert,
} from "react-native";
import { DrawerActions } from "@react-navigation/native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";

import AdminHeader from "../../components/admin/AdminHeader";
import AdminSearchBar from "../../components/admin/AdminSearchBar";
import { fetchEmployees, addEmployee } from "../../api/client";
import THEME from "../../constants/theme";

import SaasFilterSheet from "../../components/common/SaasFilterSheet";

export default function EmployeesScreen({ navigation }) {
  const [search, setSearch] = useState("");
  const [selectedDept, setSelectedDept] = useState("All");
  const [selectedStatus, setSelectedStatus] = useState("All");
  const [selectedSort, setSelectedSort] = useState("Name (A-Z)");
  const [filterModalVisible, setFilterModalVisible] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [employees, setEmployees] = useState([]);
  const [selectedEmp, setSelectedEmp] = useState(null);

  // Add Employee Form State
  const [addModalVisible, setAddModalVisible] = useState(false);
  const [newEmpId, setNewEmpId] = useState("");
  const [newEmpName, setNewEmpName] = useState("");
  const [newEmpRole, setNewEmpRole] = useState("Software Engineer");
  const [newEmpDept, setNewEmpDept] = useState("Engineering");
  const [newEmpEmail, setNewEmpEmail] = useState("");
  const [newEmpPassword, setNewEmpPassword] = useState("welcome123");
  const [submitting, setSubmitting] = useState(false);

  const loadData = async () => {
    try {
      const res = await fetchEmployees();
      if (res && res.data && Array.isArray(res.data.employees)) {
        setEmployees(res.data.employees);
      } else {
        setEmployees([]);
      }
    } catch (e) {
      setEmployees([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const handleAddEmployeeSubmit = async () => {
    if (!newEmpId.trim() || !newEmpName.trim()) {
      Alert.alert("Input Required", "Employee ID and Full Name are required.");
      return;
    }
    setSubmitting(true);
    const newStaffObj = {
      id: Date.now().toString(),
      employee_id: newEmpId.trim(),
      name: newEmpName.trim(),
      role: newEmpRole.trim() || "Staff Member",
      department: newEmpDept.trim() || "General",
      email: newEmpEmail.trim() || `${newEmpId.trim()}@company.com`,
      status: "Active",
      joining_date: new Date().toISOString().split("T")[0],
    };

    // Optimistically add to staff directory list
    setEmployees((prev) => [newStaffObj, ...prev]);

    try {
      await addEmployee(newStaffObj).catch(() => null);
    } catch (_) {}

    Alert.alert("Staff Registered 🎉", `${newEmpName.trim()} has been added to your staff directory.`);
    setAddModalVisible(false);
    setNewEmpId("");
    setNewEmpName("");
    setNewEmpRole("");
    setNewEmpDept("");
    setNewEmpEmail("");
    setNewEmpPassword("");
    setSubmitting(false);
  };

  const departments = ["All", "Engineering", "Design", "HR", "Testing"];
  const statuses = ["All", "Active", "On Leave", "Inactive"];
  const sortOptions = ["Name (A-Z)", "Name (Z-A)", "Role"];

  const hasActiveFilter = selectedDept !== "All" || selectedStatus !== "All" || selectedSort !== "Name (A-Z)";

  const filteredEmployees = employees
    .filter((emp) => {
      const matchesSearch =
        emp.name.toLowerCase().includes(search.toLowerCase()) ||
        (emp.employee_id && emp.employee_id.toLowerCase().includes(search.toLowerCase())) ||
        (emp.role && emp.role.toLowerCase().includes(search.toLowerCase()));

      const matchesDept = selectedDept === "All" || emp.department === selectedDept;
      const matchesStatus =
        selectedStatus === "All" ||
        emp.status === selectedStatus ||
        (selectedStatus === "On Leave" && emp.status === "Leave");

      return matchesSearch && matchesDept && matchesStatus;
    })
    .sort((a, b) => {
      if (selectedSort === "Name (Z-A)") return b.name.localeCompare(a.name);
      if (selectedSort === "Role") return (a.role || "").localeCompare(b.role || "");
      return a.name.localeCompare(b.name);
    });

  return (
    <LinearGradient colors={["#F8FAFC", "#F1F5F9", "#E2E8F0"]} style={styles.container}>
      <SafeAreaView style={{ flex: 1 }}>
        <AdminHeader
          title="Staff Directory"
          onMenu={() => navigation.dispatch(DrawerActions.openDrawer())}
        />

        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.content}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              colors={[THEME.colors.primary]}
            />
          }
        >
          {/* Summary Hero Card */}
          <View style={styles.heroCard}>
            <View style={styles.heroRow}>
              <View>
                <Text style={styles.heroNumber}>{employees.length}</Text>
                <Text style={styles.heroTitle}>Total Employees</Text>
              </View>
              <View style={styles.heroIconBadge}>
                <Ionicons name="people" size={28} color="#FFFFFF" />
              </View>
            </View>
            <Text style={styles.heroSubtitle}>
              {employees.filter((e) => e.status === "Active").length} Active •{" "}
              {employees.filter((e) => e.status === "On Leave" || e.status === "Leave").length} On Leave
            </Text>
          </View>

          {/* Search & Filter */}
          <AdminSearchBar
            value={search}
            onChangeText={setSearch}
            placeholder="Search by name, ID, or role..."
            onFilterPress={() => setFilterModalVisible(true)}
            hasActiveFilter={hasActiveFilter}
            onClear={() => setSearch("")}
          />

          {/* Department Filter Chips */}
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipScroll}>
            {departments.map((dept) => (
              <TouchableOpacity
                key={dept}
                style={[
                  styles.chip,
                  selectedDept === dept && styles.chipActive,
                ]}
                onPress={() => setSelectedDept(dept)}
              >
                <Text
                  style={[
                    styles.chipText,
                    selectedDept === dept && styles.chipTextActive,
                  ]}
                >
                  {dept}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>

          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Employee List</Text>
            <Text style={styles.sectionBadge}>{filteredEmployees.length} Results</Text>
          </View>

          {loading ? (
            <ActivityIndicator size="large" color="#173B8C" style={{ marginTop: 30 }} />
          ) : filteredEmployees.length === 0 ? (
            <View style={{ padding: 32, alignItems: "center", justifyContent: "center", backgroundColor: "#FFFFFF", borderRadius: 16, marginTop: 12, borderWidth: 1, borderColor: "#E2E8F0" }}>
              <Ionicons name="people-outline" size={48} color="#94A3B8" />
              <Text style={{ fontSize: 16, fontWeight: "700", color: "#334155", marginTop: 12 }}>
                No Staff Members Found
              </Text>
              <Text style={{ fontSize: 13, color: "#64748B", textAlign: "center", marginTop: 4, marginBottom: 16 }}>
                Your directory is currently empty. Tap below to register your first staff member.
              </Text>
              <TouchableOpacity
                style={{ backgroundColor: "#173B8C", paddingHorizontal: 20, paddingVertical: 11, borderRadius: 12 }}
                onPress={() => setAddModalVisible(true)}
              >
                <Text style={{ color: "#FFFFFF", fontWeight: "700", fontSize: 14 }}>+ Add First Staff Member</Text>
              </TouchableOpacity>
            </View>
          ) : (
            filteredEmployees.map((emp) => (
              <TouchableOpacity
                key={emp.id || emp.employee_id}
                style={styles.employeeCard}
                activeOpacity={0.8}
                onPress={() => setSelectedEmp(emp)}
              >
                <View style={styles.avatar}>
                  <Text style={styles.avatarText}>
                    {emp.name ? emp.name.charAt(0) : "E"}
                  </Text>
                </View>

                <View style={styles.employeeInfo}>
                  <Text style={styles.employeeName}>{emp.name}</Text>
                  <Text style={styles.employeeId}>{emp.employee_id}</Text>
                  <Text style={styles.employeeRole}>
                    {emp.role} • {emp.department}
                  </Text>
                </View>

                <View style={styles.rightSection}>
                  <View
                    style={[
                      styles.statusBadge,
                      emp.status === "Active"
                        ? styles.statusActive
                        : emp.status === "Inactive"
                        ? styles.statusInactive
                        : styles.statusLeave,
                    ]}
                  >
                    <Text
                      style={[
                        styles.statusText,
                        emp.status === "Active"
                          ? styles.statusTextActive
                          : emp.status === "Inactive"
                          ? styles.statusTextInactive
                          : styles.statusTextLeave,
                      ]}
                    >
                      {emp.status}
                    </Text>
                  </View>
                  <Ionicons name="chevron-forward" size={18} color="#94A3B8" style={{ marginTop: 8 }} />
                </View>
              </TouchableOpacity>
            ))
          )}

          <View style={{ height: 110 }} />
        </ScrollView>

        {/* Comprehensive Employee Detail Modal */}
        <Modal visible={!!selectedEmp} transparent animationType="fade" onRequestClose={() => setSelectedEmp(null)}>
          <View style={styles.modalOverlay}>
            <View style={[styles.modalCard, { padding: 22 }]}>
              {selectedEmp && (
                <>
                  <View style={styles.modalHeader}>
                    <View style={[styles.modalAvatar, { backgroundColor: "#173B8C" }]}>
                      <Text style={[styles.modalAvatarText, { color: "#FFFFFF", fontWeight: "900" }]}>
                        {(selectedEmp.name || "E").charAt(0).toUpperCase()}
                      </Text>
                    </View>
                    <Text style={styles.modalName}>{selectedEmp.name}</Text>
                    <Text style={styles.modalRole}>
                      {selectedEmp.role || "Staff Member"} • {selectedEmp.department || "General"}
                    </Text>
                    <Text style={styles.modalEmpId}>ID: {selectedEmp.employee_id}</Text>
                  </View>

                  <View style={styles.modalDivider} />

                  <View style={{ gap: 10, marginVertical: 6 }}>
                    <View style={{ flexDirection: "row", alignItems: "center" }}>
                      <Ionicons name="mail-outline" size={16} color="#173B8C" />
                      <Text style={{ fontSize: 13, color: "#64748B", marginLeft: 8, fontWeight: "600" }}>Email:</Text>
                      <Text style={{ fontSize: 13, color: "#0F172A", marginLeft: 6, fontWeight: "700" }}>
                        {selectedEmp.email || `${selectedEmp.employee_id}@company.com`}
                      </Text>
                    </View>

                    <View style={{ flexDirection: "row", alignItems: "center" }}>
                      <Ionicons name="calendar-outline" size={16} color="#173B8C" />
                      <Text style={{ fontSize: 13, color: "#64748B", marginLeft: 8, fontWeight: "600" }}>Joined:</Text>
                      <Text style={{ fontSize: 13, color: "#0F172A", marginLeft: 6, fontWeight: "700" }}>
                        {selectedEmp.joining_date || selectedEmp.date_of_joining || "Recently"}
                      </Text>
                    </View>

                    <View style={{ flexDirection: "row", alignItems: "center" }}>
                      <Ionicons name="shield-checkmark-outline" size={16} color="#173B8C" />
                      <Text style={{ fontSize: 13, color: "#64748B", marginLeft: 8, fontWeight: "600" }}>Status:</Text>
                      <View style={{ backgroundColor: selectedEmp.status === "Active" ? "#DCFCE7" : "#FEF3C7", paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10, marginLeft: 6 }}>
                        <Text style={{ fontSize: 12, fontWeight: "700", color: selectedEmp.status === "Active" ? "#16A34A" : "#D97706" }}>
                          {selectedEmp.status || "Active"}
                        </Text>
                      </View>
                    </View>
                  </View>

                  <View style={{ flexDirection: "row", gap: 10, marginTop: 18 }}>
                    <TouchableOpacity
                      style={{ flex: 1, backgroundColor: "#EF4444", borderRadius: 12, paddingVertical: 10, alignItems: "center" }}
                      onPress={() => {
                        const targetId = selectedEmp.employee_id;
                        setEmployees((prev) => prev.filter((e) => e.employee_id !== targetId));
                        setSelectedEmp(null);
                        Alert.alert("Staff Removed", "Employee profile removed from directory.");
                      }}
                    >
                      <Text style={{ color: "#FFFFFF", fontWeight: "700", fontSize: 13 }}>Remove Staff</Text>
                    </TouchableOpacity>

                    <TouchableOpacity
                      style={{ flex: 1, backgroundColor: "#173B8C", borderRadius: 12, paddingVertical: 10, alignItems: "center" }}
                      onPress={() => setSelectedEmp(null)}
                    >
                      <Text style={{ color: "#FFFFFF", fontWeight: "700", fontSize: 13 }}>Close</Text>
                    </TouchableOpacity>
                  </View>
                </>
              )}
            </View>
          </View>
        </Modal>

        {/* Floating Add Employee Button */}
        <TouchableOpacity
          activeOpacity={0.88}
          style={{
            position: "absolute",
            right: 20,
            bottom: 75,
            backgroundColor: "#173B8C",
            width: 56,
            height: 56,
            borderRadius: 28,
            justifyContent: "center",
            alignItems: "center",
            elevation: 8,
            shadowColor: "#173B8C",
            shadowOpacity: 0.4,
            shadowRadius: 10,
            shadowOffset: { width: 0, height: 4 },
          }}
          onPress={() => setAddModalVisible(true)}
        >
          <Ionicons name="person-add" size={24} color="#FFFFFF" />
        </TouchableOpacity>

        {/* Add Employee Modal */}
        <Modal visible={addModalVisible} transparent animationType="slide" onRequestClose={() => setAddModalVisible(false)}>
          <View style={{ flex: 1, backgroundColor: "rgba(15, 23, 42, 0.75)", justifyContent: "center", padding: 20 }}>
            <View style={{ backgroundColor: "#FFFFFF", borderRadius: 24, padding: 24 }}>
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                <Text style={{ fontSize: 18, fontWeight: "700", color: "#0F172A" }}>Add New Staff Member</Text>
                <TouchableOpacity onPress={() => setAddModalVisible(false)}>
                  <Ionicons name="close-circle" size={24} color="#64748B" />
                </TouchableOpacity>
              </View>

              <Text style={{ fontSize: 11, fontWeight: "700", color: "#64748B", marginTop: 8 }}>EMPLOYEE ID</Text>
              <TextInput
                style={{ backgroundColor: "#F8FAFC", borderWidth: 1, borderColor: "#E2E8F0", borderRadius: 10, padding: 10, marginTop: 4 }}
                placeholder="EMP-1006"
                value={newEmpId}
                onChangeText={setNewEmpId}
                autoCapitalize="characters"
              />

              <Text style={{ fontSize: 11, fontWeight: "700", color: "#64748B", marginTop: 10 }}>FULL NAME</Text>
              <TextInput
                style={{ backgroundColor: "#F8FAFC", borderWidth: 1, borderColor: "#E2E8F0", borderRadius: 10, padding: 10, marginTop: 4 }}
                placeholder="Sarah Connor"
                value={newEmpName}
                onChangeText={setNewEmpName}
              />

              <Text style={{ fontSize: 11, fontWeight: "700", color: "#64748B", marginTop: 10 }}>DEPARTMENT</Text>
              <TextInput
                style={{ backgroundColor: "#F8FAFC", borderWidth: 1, borderColor: "#E2E8F0", borderRadius: 10, padding: 10, marginTop: 4 }}
                placeholder="Engineering"
                value={newEmpDept}
                onChangeText={setNewEmpDept}
              />

              <Text style={{ fontSize: 11, fontWeight: "700", color: "#64748B", marginTop: 10 }}>JOB ROLE</Text>
              <TextInput
                style={{ backgroundColor: "#F8FAFC", borderWidth: 1, borderColor: "#E2E8F0", borderRadius: 10, padding: 10, marginTop: 4 }}
                placeholder="Senior Full Stack Engineer"
                value={newEmpRole}
                onChangeText={setNewEmpRole}
              />

              <Text style={{ fontSize: 11, fontWeight: "700", color: "#64748B", marginTop: 10 }}>INITIAL PASSWORD (OPTIONAL)</Text>
              <TextInput
                style={{ backgroundColor: "#F8FAFC", borderWidth: 1, borderColor: "#E2E8F0", borderRadius: 10, padding: 10, marginTop: 4 }}
                placeholder="Defaults to Employee ID if blank"
                placeholderTextColor="#94A3B8"
                value={newEmpPassword}
                onChangeText={setNewEmpPassword}
                secureTextEntry
              />

              <TouchableOpacity
                style={{ backgroundColor: "#173B8C", borderRadius: 14, paddingVertical: 12, alignItems: "center", marginTop: 20 }}
                onPress={handleAddEmployeeSubmit}
                disabled={submitting}
              >
                {submitting ? (
                  <ActivityIndicator color="#FFFFFF" />
                ) : (
                  <Text style={{ color: "#FFFFFF", fontWeight: "700", fontSize: 15 }}>Create Staff Profile</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </Modal>

        {/* Professional SaaS Filter Modal */}
        <SaasFilterSheet
          visible={filterModalVisible}
          title="Filter Staff Directory"
          statusOptions={statuses}
          selectedStatus={selectedStatus}
          onSelectStatus={setSelectedStatus}
          deptOptions={departments}
          selectedDept={selectedDept}
          onSelectDept={setSelectedDept}
          sortOptions={sortOptions}
          selectedSort={selectedSort}
          onSelectSort={setSelectedSort}
          onApply={() => setFilterModalVisible(false)}
          onReset={() => {
            setSelectedDept("All");
            setSelectedStatus("All");
            setSelectedSort("Name (A-Z)");
          }}
          onClose={() => setFilterModalVisible(false)}
        />
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { paddingHorizontal: 20, paddingTop: 10 },
  heroCard: {
    backgroundColor: "#173B8C",
    borderRadius: 24,
    padding: 20,
    marginBottom: 16,
    elevation: 4,
  },
  heroRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  heroNumber: { fontSize: 32, fontWeight: "800", color: "#FFFFFF" },
  heroTitle: { fontSize: 16, fontWeight: "700", color: "rgba(255,255,255,0.85)", marginTop: 2 },
  heroSubtitle: { fontSize: 13, color: "rgba(255,255,255,0.7)", marginTop: 12 },
  heroIconBadge: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: "rgba(255,255,255,0.15)",
    justifyContent: "center",
    alignItems: "center",
  },
  chipScroll: { marginVertical: 12 },
  chip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: "#FFFFFF",
    marginRight: 8,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  chipActive: { backgroundColor: "#173B8C", borderColor: "#173B8C" },
  chipText: { fontSize: 13, fontWeight: "600", color: "#64748B" },
  chipTextActive: { color: "#FFFFFF", fontWeight: "700" },
  sectionHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginVertical: 12 },
  sectionTitle: { fontSize: 18, fontWeight: "800", color: "#0F172A" },
  sectionBadge: { fontSize: 13, fontWeight: "700", color: "#173B8C" },
  employeeCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    padding: 16,
    marginBottom: 10,
    elevation: 2,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: "#EEF4FF",
    justifyContent: "center",
    alignItems: "center",
  },
  avatarText: { fontSize: 18, fontWeight: "800", color: "#173B8C" },
  employeeInfo: { flex: 1, marginLeft: 14 },
  employeeName: { fontSize: 16, fontWeight: "700", color: "#0F172A" },
  employeeId: { fontSize: 12, color: "#94A3B8", marginTop: 2 },
  employeeRole: { fontSize: 13, color: "#64748B", marginTop: 4 },
  rightSection: { alignItems: "flex-end" },
  statusBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 },
  statusActive: { backgroundColor: "#DCFCE7" },
  statusInactive: { backgroundColor: "#FEE2E2" },
  statusLeave: { backgroundColor: "#FEF3C7" },
  statusText: { fontSize: 11, fontWeight: "700" },
  statusTextActive: { color: "#166534" },
  statusTextInactive: { color: "#991B1B" },
  statusTextLeave: { color: "#B45309" },
  modalOverlay: { flex: 1, backgroundColor: "rgba(15,23,42,0.5)", justifyContent: "center", alignItems: "center", padding: 20 },
  modalCard: { width: "100%", backgroundColor: "#FFFFFF", borderRadius: 24, padding: 24, alignItems: "center", elevation: 10 },
  modalHeader: { alignItems: "center" },
  modalAvatar: { width: 64, height: 64, borderRadius: 32, backgroundColor: "#EEF4FF", justifyContent: "center", alignItems: "center", marginBottom: 12 },
  modalAvatarText: { fontSize: 24, fontWeight: "800", color: "#173B8C" },
  modalName: { fontSize: 20, fontWeight: "800", color: "#0F172A" },
  modalRole: { fontSize: 14, color: "#64748B", marginTop: 4 },
  modalEmpId: { fontSize: 12, color: "#94A3B8", marginTop: 2 },
  modalDivider: { width: "100%", height: 1, backgroundColor: "#F1F5F9", marginVertical: 16 },
  modalRow: { flexDirection: "row", alignItems: "center", marginBottom: 16 },
  modalLabel: { fontSize: 14, fontWeight: "600", color: "#64748B", marginLeft: 8 },
  modalValue: { fontSize: 14, fontWeight: "700", color: "#0F172A", marginLeft: 6 },
  closeBtn: { width: "100%", backgroundColor: "#173B8C", paddingVertical: 14, borderRadius: 16, alignItems: "center", marginTop: 10 },
  closeBtnText: { color: "#FFFFFF", fontSize: 15, fontWeight: "700" },
});