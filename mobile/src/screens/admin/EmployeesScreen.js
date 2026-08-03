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
} from "react-native";
import { DrawerActions } from "@react-navigation/native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";

import AdminHeader from "../../components/admin/AdminHeader";
import AdminSearchBar from "../../components/admin/AdminSearchBar";
import { fetchEmployees } from "../../api/client";
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

  const fallbackEmployees = [
    { id: "1", employee_id: "EMP-1001", name: "Rahul Kumar", role: "Software Engineer", department: "Engineering", status: "Active" },
    { id: "2", employee_id: "EMP-1002", name: "Priya Sharma", role: "UI/UX Designer", department: "Design", status: "On Leave" },
    { id: "3", employee_id: "EMP-1003", name: "Arjun Joshi", role: "HR Manager", department: "HR", status: "Active" },
    { id: "4", employee_id: "EMP-1004", name: "Vikram Nair", role: "QA Engineer", department: "Testing", status: "Inactive" },
    { id: "5", employee_id: "EMP-1005", name: "Ananya Patel", role: "DevOps Engineer", department: "Engineering", status: "Active" },
  ];

  const loadData = async () => {
    try {
      const res = await fetchEmployees();
      if (res && res.data && Array.isArray(res.data.employees)) {
        setEmployees(res.data.employees);
      } else {
        setEmployees(fallbackEmployees);
      }
    } catch (e) {
      setEmployees(fallbackEmployees);
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

        {/* Employee Detail Modal */}
        <Modal visible={!!selectedEmp} transparent animationType="fade">
          <View style={styles.modalOverlay}>
            <View style={styles.modalCard}>
              {selectedEmp && (
                <>
                  <View style={styles.modalHeader}>
                    <View style={styles.modalAvatar}>
                      <Text style={styles.modalAvatarText}>
                        {selectedEmp.name.charAt(0)}
                      </Text>
                    </View>
                    <Text style={styles.modalName}>{selectedEmp.name}</Text>
                    <Text style={styles.modalRole}>
                      {selectedEmp.role} • {selectedEmp.department}
                    </Text>
                    <Text style={styles.modalEmpId}>{selectedEmp.employee_id}</Text>
                  </View>

                  <View style={styles.modalDivider} />

                  <View style={styles.modalRow}>
                    <Ionicons name="shield-checkmark-outline" size={18} color="#173B8C" />
                    <Text style={styles.modalLabel}>Status:</Text>
                    <Text style={styles.modalValue}>{selectedEmp.status}</Text>
                  </View>

                  <TouchableOpacity
                    style={styles.closeBtn}
                    onPress={() => setSelectedEmp(null)}
                  >
                    <Text style={styles.closeBtnText}>Close</Text>
                  </TouchableOpacity>
                </>
              )}
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