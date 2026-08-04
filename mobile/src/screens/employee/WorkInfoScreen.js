import React, { useState, useEffect } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  SafeAreaView,
  ActivityIndicator,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../../store/AuthContext";
import { fetchEmployeeProfile } from "../../api/client";
import ProfileHeader from "../../components/profile/ProfileHeader";
import DetailCard from "../../components/profile/DetailCard";

export default function WorkInfoScreen() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [workInfo, setWorkInfo] = useState({
    employeeId: user?.employeeId || user?.employee_id || "EMP-1001",
    employeeName: user?.name || "Staff Member",
    designation: user?.role || "Software Engineer",
    department: user?.department || "Engineering",
    employmentType: "Full Time",
    joiningDate: user?.joining_date || "Recently Joined",
    reportingManager: user?.manager_name || "Department Head",
    employeeStatus: "Active",
    workLocation: "Corporate HQ",
    workMode: user?.work_mode || "Office",
    officeEmail: user?.email || `${user?.employeeId || "emp"}@company.com`,
  });

  useEffect(() => {
    fetchEmployeeProfile()
      .then((res) => {
        if (res?.data?.ok && res?.data?.profile) {
          const p = res.data.profile;
          setWorkInfo({
            employeeId: p.employee_id || user?.employeeId || "EMP-1001",
            employeeName: p.name || user?.name || "Staff Member",
            designation: p.role || user?.role || "Software Engineer",
            department: p.department || user?.department || "Engineering",
            employmentType: p.employment_type || "Full Time",
            joiningDate: p.date_of_joining || p.joining_date || "Recently Joined",
            reportingManager: p.manager_name || "Department Head",
            employeeStatus: p.status || "Active",
            workLocation: p.work_location || "Corporate HQ",
            workMode: p.work_mode || "Office",
            officeEmail: p.email || `${p.employee_id}@company.com`,
          });
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <SafeAreaView style={styles.container}>
      <ProfileHeader title="Work Information" showBack />

      {loading ? (
        <View style={{ flex: 1, justifyContent: "center", alignItems: "center" }}>
          <ActivityIndicator size="large" color="#173B8C" />
        </View>
      ) : (
        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
          {/* Summary Card */}
          <View style={styles.summaryCard}>
            <View style={styles.avatar}>
              <Ionicons name="briefcase" size={24} color="#FFFFFF" />
            </View>

            <View style={styles.summaryText}>
              <Text style={styles.name}>{workInfo.employeeName}</Text>
              <Text style={styles.subText}>{workInfo.designation} • {workInfo.department}</Text>
            </View>
          </View>

          {/* Details */}
          <DetailCard icon="id-card-outline" label="Employee ID" value={workInfo.employeeId} />
          <DetailCard icon="briefcase-outline" label="Designation" value={workInfo.designation} />
          <DetailCard icon="business-outline" label="Department" value={workInfo.department} />
          <DetailCard icon="calendar-outline" label="Joining Date" value={workInfo.joiningDate} />
          <DetailCard icon="person-outline" label="Reporting Manager" value={workInfo.reportingManager} />
          <DetailCard icon="shield-checkmark-outline" label="Status" value={workInfo.employeeStatus} />
          <DetailCard icon="laptop-outline" label="Work Mode" value={workInfo.workMode} />
          <DetailCard icon="mail-outline" label="Office Email" value={workInfo.officeEmail} />
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F8FAFC" },
  content: { padding: 18, paddingBottom: 40 },
  summaryCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: "#173B8C",
    justifyContent: "center",
    alignItems: "center",
    marginRight: 14,
  },
  summaryText: { flex: 1 },
  name: { fontSize: 16, fontWeight: "800", color: "#0F172A" },
  subText: { fontSize: 13, fontWeight: "600", color: "#64748B", marginTop: 2 },
});