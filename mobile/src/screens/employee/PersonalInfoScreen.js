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

export default function PersonalInfoScreen() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [modalVisible, setModalVisible] = useState(false);

  const [profile, setProfile] = useState({
    employeeId: user?.employeeId || user?.employee_id || "",
    fullName: user?.name || "",
    gender: user?.gender || "Not Specified",
    dob: user?.dob || "Not Specified",
    bloodGroup: user?.blood_group || "Not Specified",
    maritalStatus: "Single",
    nationality: "Indian",
    fatherName: "Not Specified",
  });

  const [editGender, setEditGender] = useState(profile.gender);
  const [editDob, setEditDob] = useState(profile.dob);
  const [editBloodGroup, setEditBloodGroup] = useState(profile.bloodGroup);
  const [editMaritalStatus, setEditMaritalStatus] = useState(profile.maritalStatus);
  const [editNationality, setEditNationality] = useState(profile.nationality);
  const [editFatherName, setEditFatherName] = useState(profile.fatherName);

  useEffect(() => {
    fetchEmployeeProfile()
      .then((res) => {
        if (res?.data?.ok && res?.data?.profile) {
          const p = res.data.profile;
          const updated = {
            employeeId: p.employee_id || user?.employeeId || "",
            fullName: p.name || user?.name || "",
            gender: p.gender || "Not Specified",
            dob: p.dob || "Not Specified",
            bloodGroup: p.blood_group || "Not Specified",
            maritalStatus: p.marital_status || "Single",
            nationality: p.nationality || "Indian",
            fatherName: p.father_name || "Not Specified",
          };
          setProfile(updated);
          setEditGender(updated.gender);
          setEditDob(updated.dob);
          setEditBloodGroup(updated.bloodGroup);
          setEditMaritalStatus(updated.maritalStatus);
          setEditNationality(updated.nationality);
          setEditFatherName(updated.fatherName);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSave = () => {
    setProfile((prev) => ({
      ...prev,
      gender: editGender.trim() || "Not Specified",
      dob: editDob.trim() || "Not Specified",
      bloodGroup: editBloodGroup.trim() || "Not Specified",
      maritalStatus: editMaritalStatus.trim() || "Single",
      nationality: editNationality.trim() || "Indian",
      fatherName: editFatherName.trim() || "Not Specified",
    }));

    Alert.alert("Updated 🎉", "Personal information updated successfully.");
    setModalVisible(false);
  };

  return (
    <SafeAreaView style={styles.container}>
      <ProfileHeader title="Personal Information" showBack />

      {loading ? (
        <View style={{ flex: 1, justifyContent: "center", alignItems: "center" }}>
          <ActivityIndicator size="large" color="#173B8C" />
        </View>
      ) : (
        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
          {/* Summary Card */}
          <View style={styles.summaryCard}>
            <View style={styles.avatar}>
              <Text style={{ fontSize: 18, fontWeight: "900", color: "#FFFFFF" }}>
                {profile.fullName.charAt(0).toUpperCase()}
              </Text>
            </View>

            <View style={styles.summaryText}>
              <Text style={styles.name}>{profile.fullName}</Text>
              <Text style={styles.idText}>ID • {profile.employeeId}</Text>
            </View>

            <TouchableOpacity style={styles.editBtn} onPress={() => setModalVisible(true)}>
              <Ionicons name="create-outline" size={20} color="#173B8C" />
            </TouchableOpacity>
          </View>

          {/* Details */}
          <DetailCard icon="id-card-outline" label="Employee ID" value={profile.employeeId} />
          <DetailCard icon="person-outline" label="Full Name" value={profile.fullName} />
          <DetailCard icon="male-female-outline" label="Gender" value={profile.gender} />
          <DetailCard icon="calendar-outline" label="Date of Birth" value={profile.dob} />
          <DetailCard icon="water-outline" label="Blood Group" value={profile.bloodGroup} />
          <DetailCard icon="heart-outline" label="Marital Status" value={profile.maritalStatus} />
          <DetailCard icon="flag-outline" label="Nationality" value={profile.nationality} />
          <DetailCard icon="people-outline" label="Father's / Guardian's Name" value={profile.fatherName} />
        </ScrollView>
      )}

      {/* Edit Personal Info Modal */}
      <Modal visible={modalVisible} transparent animationType="slide" onRequestClose={() => setModalVisible(false)}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Edit Personal Info</Text>
              <TouchableOpacity onPress={() => setModalVisible(false)}>
                <Ionicons name="close-circle" size={24} color="#64748B" />
              </TouchableOpacity>
            </View>

            <Text style={styles.inputLabel}>GENDER</Text>
            <TextInput style={styles.input} value={editGender} onChangeText={setEditGender} placeholder="Male / Female / Other" />

            <Text style={styles.inputLabel}>DATE OF BIRTH</Text>
            <TextInput style={styles.input} value={editDob} onChangeText={setEditDob} placeholder="YYYY-MM-DD" />

            <Text style={styles.inputLabel}>BLOOD GROUP</Text>
            <TextInput style={styles.input} value={editBloodGroup} onChangeText={setEditBloodGroup} placeholder="e.g. O+" />

            <Text style={styles.inputLabel}>MARITAL STATUS</Text>
            <TextInput style={styles.input} value={editMaritalStatus} onChangeText={setEditMaritalStatus} placeholder="Single / Married" />

            <Text style={styles.inputLabel}>FATHER'S / GUARDIAN'S NAME</Text>
            <TextInput style={styles.input} value={editFatherName} onChangeText={setEditFatherName} placeholder="Full Name" />

            <TouchableOpacity style={styles.saveModalBtn} onPress={handleSave}>
              <Text style={styles.saveModalBtnText}>Save Personal Details</Text>
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
  idText: { fontSize: 12, fontWeight: "600", color: "#64748B", marginTop: 2 },
  editBtn: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: "#EEF4FF",
    justifyContent: "center",
    alignItems: "center",
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