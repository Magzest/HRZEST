import React, { useState, useEffect } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  SafeAreaView,
  ActivityIndicator,
  TouchableOpacity,
  Modal,
  TextInput,
  Alert,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../../store/AuthContext";
import { fetchEmployeeProfile } from "../../api/client";
import ProfileHeader from "../../components/profile/ProfileHeader";
import DetailCard from "../../components/profile/DetailCard";

export default function WorkInfoScreen() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [modalVisible, setModalVisible] = useState(false);

  const [workInfo, setWorkInfo] = useState({
    employeeId: user?.employeeId || user?.employee_id || "",
    employeeName: user?.name || "",
    designation: user?.role || "Software Engineer",
    department: user?.department || "Engineering",
    employmentType: "Full-Time",
    joiningDate: user?.joining_date || "2023-01-15",
    reportingManager: user?.manager_name || "Engineering Lead",
    employeeStatus: "Active",
    workLocation: "Headquarters",
    workMode: user?.work_mode || "Hybrid",
    officeEmail: user?.email || "",
  });

  const [editDesignation, setEditDesignation] = useState(workInfo.designation);
  const [editDepartment, setEditDepartment] = useState(workInfo.department);
  const [editJoiningDate, setEditJoiningDate] = useState(workInfo.joiningDate);
  const [editManager, setEditManager] = useState(workInfo.reportingManager);
  const [editWorkMode, setEditWorkMode] = useState(workInfo.workMode);
  const [editWorkLocation, setEditWorkLocation] = useState(workInfo.workLocation);

  useEffect(() => {
    fetchEmployeeProfile()
      .then((res) => {
        if (res?.data?.ok && res?.data?.profile) {
          const p = res.data.profile;
          const updated = {
            employeeId: p.employee_id || user?.employeeId || "",
            employeeName: p.name || user?.name || "",
            designation: p.role || user?.role || "Software Engineer",
            department: p.department || user?.department || "Engineering",
            employmentType: p.employment_type || "Full-Time",
            joiningDate: p.join_date || p.date_of_joining || p.joining_date || "2023-01-15",
            reportingManager: p.manager_name || "Engineering Lead",
            employeeStatus: p.status || "Active",
            workLocation: p.work_location || "Headquarters",
            workMode: p.work_mode || "Hybrid",
            officeEmail: p.email || "",
          };
          setWorkInfo(updated);
          setEditDesignation(updated.designation);
          setEditDepartment(updated.department);
          setEditJoiningDate(updated.joiningDate);
          setEditManager(updated.reportingManager);
          setEditWorkMode(updated.workMode);
          setEditWorkLocation(updated.workLocation);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSave = () => {
    setWorkInfo((prev) => ({
      ...prev,
      designation: editDesignation.trim() || prev.designation,
      department: editDepartment.trim() || prev.department,
      joiningDate: editJoiningDate.trim() || prev.joiningDate,
      reportingManager: editManager.trim() || prev.reportingManager,
      workMode: editWorkMode.trim() || prev.workMode,
      workLocation: editWorkLocation.trim() || prev.workLocation,
    }));

    Alert.alert("Updated 🎉", "Work Information updated successfully.");
    setModalVisible(false);
  };

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

            <TouchableOpacity style={styles.editBtn} onPress={() => setModalVisible(true)}>
              <Ionicons name="create-outline" size={20} color="#173B8C" />
            </TouchableOpacity>
          </View>

          {/* Details */}
          <DetailCard icon="id-card-outline" label="Employee ID" value={workInfo.employeeId} />
          <DetailCard icon="briefcase-outline" label="Designation / Role" value={workInfo.designation} />
          <DetailCard icon="business-outline" label="Department" value={workInfo.department} />
          <DetailCard icon="calendar-outline" label="Date of Joining" value={workInfo.joiningDate} />
          <DetailCard icon="person-outline" label="Reporting Manager" value={workInfo.reportingManager} />
          <DetailCard icon="shield-checkmark-outline" label="Employee Status" value={workInfo.employeeStatus} />
          <DetailCard icon="laptop-outline" label="Work Mode" value={workInfo.workMode} />
          <DetailCard icon="location-outline" label="Work Location" value={workInfo.workLocation} />
          <DetailCard icon="mail-outline" label="Office Email" value={workInfo.officeEmail} />

          <View style={styles.infoNoteCard}>
            <Ionicons name="information-circle-outline" size={18} color="#173B8C" style={{ marginRight: 8 }} />
            <Text style={styles.infoNoteText}>
              Official role assignments are synchronized with organization records.
            </Text>
          </View>

          <View style={{ height: 40 }} />
        </ScrollView>
      )}

      {/* Edit Work Info Modal */}
      <Modal visible={modalVisible} transparent animationType="slide" onRequestClose={() => setModalVisible(false)}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Edit Work Information</Text>
              <TouchableOpacity onPress={() => setModalVisible(false)}>
                <Ionicons name="close-circle" size={24} color="#64748B" />
              </TouchableOpacity>
            </View>

            <Text style={styles.inputLabel}>DESIGNATION / ROLE</Text>
            <TextInput style={styles.input} value={editDesignation} onChangeText={setEditDesignation} />

            <Text style={styles.inputLabel}>DEPARTMENT</Text>
            <TextInput style={styles.input} value={editDepartment} onChangeText={setEditDepartment} />

            <Text style={styles.inputLabel}>JOINING DATE</Text>
            <TextInput style={styles.input} value={editJoiningDate} onChangeText={setEditJoiningDate} placeholder="YYYY-MM-DD" />

            <Text style={styles.inputLabel}>REPORTING MANAGER</Text>
            <TextInput style={styles.input} value={editManager} onChangeText={setEditManager} />

            <Text style={styles.inputLabel}>WORK MODE</Text>
            <TextInput style={styles.input} value={editWorkMode} onChangeText={setEditWorkMode} placeholder="Hybrid / On-site / Remote" />

            <Text style={styles.inputLabel}>WORK LOCATION</Text>
            <TextInput style={styles.input} value={editWorkLocation} onChangeText={setEditWorkLocation} />

            <TouchableOpacity style={styles.saveModalBtn} onPress={handleSave}>
              <Text style={styles.saveModalBtnText}>Save Work Details</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F8FAFC" },
  content: { padding: 18, paddingBottom: 130 },
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
  name: { fontSize: 14, fontWeight: "800", color: "#0F172A" },
  subText: { fontSize: 12, fontWeight: "600", color: "#64748B", marginTop: 2 },
  editBtn: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: "#EEF4FF",
    justifyContent: "center",
    alignItems: "center",
  },
  infoNoteCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#EEF4FF",
    borderRadius: 14,
    padding: 14,
    marginTop: 14,
    borderWidth: 1,
    borderColor: "#DBEAFE",
  },
  infoNoteText: {
    flex: 1,
    fontSize: 12,
    color: "#1E3A8A",
    fontWeight: "600",
    lineHeight: 18,
  },
  modalOverlay: { flex: 1, backgroundColor: "rgba(15, 23, 42, 0.75)", justifyContent: "center", padding: 20 },
  modalContent: { backgroundColor: "#FFFFFF", borderRadius: 24, padding: 24 },
  modalHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 16 },
  modalTitle: { fontSize: 16, fontWeight: "800", color: "#0F172A" },
  inputLabel: { fontSize: 11, fontWeight: "700", color: "#64748B", marginTop: 10 },
  input: {
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    borderRadius: 10,
    padding: 10,
    marginTop: 4,
    fontSize: 14,
    color: "#0F172A",
  },
  saveModalBtn: {
    backgroundColor: "#173B8C",
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 20,
  },
  saveModalBtnText: { color: "#FFFFFF", fontWeight: "700", fontSize: 15 },
});