import React, { useState } from "react";
import {
  SafeAreaView,
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  FlatList,
} from "react-native";
import { DrawerActions } from "@react-navigation/native";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";

import AdminHeader from "../../components/admin/AdminHeader";
import AdminSearchBar from "../../components/admin/AdminSearchBar";

export default function AttendanceScreen({ navigation }) {
  const [search, setSearch] = useState("");
  const [month, setMonth] = useState("July");
  const [year, setYear] = useState("2026");

  const summary = {
    employees: 254,
    workingDays: 26,
    attendance: 94,
    holidays: 2,
  };

  const employees = [
    { id: "EMP001", name: "Rahul Kumar", full: 24, late: 1, half: 1, absent: 0, working: 26, percent: 96 },
    { id: "EMP002", name: "Priya Sharma", full: 22, late: 2, half: 0, absent: 2, working: 26, percent: 88 },
    { id: "EMP003", name: "Arjun Joshi", full: 25, late: 1, half: 0, absent: 0, working: 26, percent: 98 },
    { id: "EMP004", name: "Vikram Nair", full: 20, late: 3, half: 2, absent: 1, working: 26, percent: 85 },
  ];

  const filteredEmployees = employees.filter(
    (e) =>
      e.name.toLowerCase().includes(search.toLowerCase()) ||
      e.id.toLowerCase().includes(search.toLowerCase())
  );

  const renderEmployee = ({ item }) => (
    <View style={styles.employeeCard}>
      <View style={styles.employeeHeader}>
        <View>
          <Text style={styles.employeeName}>{item.name}</Text>
          <Text style={styles.employeeId}>{item.id}</Text>
        </View>

        <View style={styles.percentBadge}>
          <Text style={styles.percentText}>{item.percent}%</Text>
        </View>
      </View>

      <View style={styles.progressBackground}>
        <View style={[styles.progressFill, { width: `${item.percent}%` }]} />
      </View>

      <View style={styles.statsRow}>
        <View style={styles.statChipGreen}>
          <Text style={styles.chipValue}>{item.full}</Text>
          <Text style={styles.chipLabel}>Full</Text>
        </View>

        <View style={styles.statChipOrange}>
          <Text style={styles.chipValue}>{item.late}</Text>
          <Text style={styles.chipLabel}>Late</Text>
        </View>

        <View style={styles.statChipBlue}>
          <Text style={styles.chipValue}>{item.half}</Text>
          <Text style={styles.chipLabel}>Half</Text>
        </View>

        <View style={styles.statChipRed}>
          <Text style={styles.chipValue}>{item.absent}</Text>
          <Text style={styles.chipLabel}>Absent</Text>
        </View>
      </View>
    </View>
  );

  return (
    <LinearGradient colors={["#F8FAFC", "#F3F7FD", "#EDF4FF"]} style={styles.container}>
      <SafeAreaView style={{ flex: 1 }}>
        <AdminHeader
          title="Daily Attendance"
          onMenu={() => navigation.dispatch(DrawerActions.openDrawer())}
        />

        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
          {/* Quick Mark Attendance Banner */}
          <TouchableOpacity
            style={styles.markBanner}
            activeOpacity={0.85}
            onPress={() => navigation.navigate("AdminTabs", { screen: "MarkAttendance" })}
          >
            <View style={styles.markBannerLeft}>
              <Ionicons name="create-outline" size={24} color="#FFFFFF" />
              <View style={{ marginLeft: 12 }}>
                <Text style={styles.markBannerTitle}>Mark Bulk Attendance</Text>
                <Text style={styles.markBannerSub}>Quick manual attendance entry for staff</Text>
              </View>
            </View>
            <Ionicons name="chevron-forward" size={20} color="#FFFFFF" />
          </TouchableOpacity>

          {/* Search */}
          <AdminSearchBar
            value={search}
            onChangeText={setSearch}
            placeholder="Search employee by name or ID..."
          />

          {/* Summary Grid */}
          <View style={styles.summaryGrid}>
            <View style={styles.summaryCard}>
              <Ionicons name="people" size={24} color="#2563EB" />
              <Text style={styles.summaryValue}>{summary.employees}</Text>
              <Text style={styles.summaryLabel}>Total Staff</Text>
            </View>

            <View style={styles.summaryCard}>
              <Ionicons name="calendar" size={24} color="#16A34A" />
              <Text style={styles.summaryValue}>{summary.workingDays}</Text>
              <Text style={styles.summaryLabel}>Working Days</Text>
            </View>

            <View style={styles.summaryCard}>
              <Ionicons name="checkmark-circle" size={24} color="#F59E0B" />
              <Text style={styles.summaryValue}>{summary.attendance}%</Text>
              <Text style={styles.summaryLabel}>Avg Attendance</Text>
            </View>

            <View style={styles.summaryCard}>
              <Ionicons name="gift" size={24} color="#EF4444" />
              <Text style={styles.summaryValue}>{summary.holidays}</Text>
              <Text style={styles.summaryLabel}>Holidays</Text>
            </View>
          </View>

          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Employee Records</Text>
            <Text style={styles.sectionBadge}>{filteredEmployees.length} Found</Text>
          </View>

          <FlatList
            data={filteredEmployees}
            keyExtractor={(item) => item.id}
            renderItem={renderEmployee}
            scrollEnabled={false}
          />

          <View style={{ height: 110 }} />
        </ScrollView>
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { paddingHorizontal: 20, paddingTop: 10 },
  markBanner: {
    backgroundColor: "#173B8C",
    borderRadius: 20,
    padding: 16,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 14,
    elevation: 3,
  },
  markBannerLeft: { flexDirection: "row", alignItems: "center" },
  markBannerTitle: { color: "#FFFFFF", fontSize: 16, fontWeight: "800" },
  markBannerSub: { color: "rgba(255,255,255,0.75)", fontSize: 12, marginTop: 2 },
  summaryGrid: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between", marginVertical: 14 },
  summaryCard: {
    width: "48%",
    backgroundColor: "#FFFFFF",
    borderRadius: 18,
    paddingVertical: 16,
    alignItems: "center",
    marginBottom: 12,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    elevation: 2,
  },
  summaryValue: { marginTop: 8, fontSize: 24, fontWeight: "800", color: "#0F172A" },
  summaryLabel: { marginTop: 4, fontSize: 12, color: "#64748B", fontWeight: "600" },
  sectionHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 12 },
  sectionTitle: { fontSize: 18, fontWeight: "800", color: "#0F172A" },
  sectionBadge: { fontSize: 13, fontWeight: "700", color: "#173B8C" },
  employeeCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    elevation: 2,
  },
  employeeHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 12 },
  employeeName: { fontSize: 16, fontWeight: "700", color: "#0F172A" },
  employeeId: { marginTop: 2, fontSize: 12, color: "#64748B", fontWeight: "500" },
  percentBadge: { borderRadius: 14, backgroundColor: "#DBEAFE", paddingHorizontal: 10, paddingVertical: 4 },
  percentText: { color: "#173B8C", fontWeight: "800", fontSize: 13 },
  progressBackground: { width: "100%", height: 8, borderRadius: 4, backgroundColor: "#E2E8F0", overflow: "hidden", marginBottom: 14 },
  progressFill: { height: "100%", borderRadius: 4, backgroundColor: "#22C55E" },
  statsRow: { flexDirection: "row", justifyContent: "space-between" },
  statChipGreen: { width: "23%", borderRadius: 12, backgroundColor: "#ECFDF5", alignItems: "center", paddingVertical: 8 },
  statChipOrange: { width: "23%", borderRadius: 12, backgroundColor: "#FFF7ED", alignItems: "center", paddingVertical: 8 },
  statChipBlue: { width: "23%", borderRadius: 12, backgroundColor: "#EFF6FF", alignItems: "center", paddingVertical: 8 },
  statChipRed: { width: "23%", borderRadius: 12, backgroundColor: "#FEF2F2", alignItems: "center", paddingVertical: 8 },
  chipValue: { fontSize: 16, fontWeight: "800", color: "#0F172A" },
  chipLabel: { marginTop: 2, fontSize: 11, color: "#64748B", fontWeight: "600" },
});