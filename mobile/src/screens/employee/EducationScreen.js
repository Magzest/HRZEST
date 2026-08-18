import React, { useState } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  SafeAreaView,
  Modal,
  TextInput,
  Alert,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";

import ProfileHeader from "../../components/profile/ProfileHeader";
import SaveButton from "../../components/profile/SaveButton";

export default function EducationScreen() {
  const [education, setEducation] = useState([
    {
      id: "1",
      degree: "Bachelor of Technology",
      specialization: "Computer Science & Engineering",
      institution: "State Technological University",
      duration: "2018 - 2022",
      grade: "8.8 CGPA",
      status: "Completed",
    },
  ]);

  const [modalVisible, setModalVisible] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const [degree, setDegree] = useState("");
  const [specialization, setSpecialization] = useState("");
  const [institution, setInstitution] = useState("");
  const [duration, setDuration] = useState("");
  const [grade, setGrade] = useState("");

  const handleOpenAdd = () => {
    setEditingItem(null);
    setDegree("");
    setSpecialization("");
    setInstitution("");
    setDuration("");
    setGrade("");
    setModalVisible(true);
  };

  const handleOpenEdit = (item) => {
    setEditingItem(item);
    setDegree(item.degree);
    setSpecialization(item.specialization);
    setInstitution(item.institution);
    setDuration(item.duration);
    setGrade(item.grade);
    setModalVisible(true);
  };

  const handleSave = () => {
    if (!degree.trim() || !institution.trim()) {
      Alert.alert("Input Required", "Degree and Institution are required fields.");
      return;
    }

    if (editingItem) {
      setEducation((prev) =>
        prev.map((e) =>
          e.id === editingItem.id
            ? {
                ...e,
                degree: degree.trim(),
                specialization: specialization.trim(),
                institution: institution.trim(),
                duration: duration.trim(),
                grade: grade.trim(),
              }
            : e
        )
      );
      Alert.alert("Updated 🎉", "Qualification updated successfully.");
    } else {
      const newItem = {
        id: Date.now().toString(),
        degree: degree.trim(),
        specialization: specialization.trim() || "General",
        institution: institution.trim(),
        duration: duration.trim() || "N/A",
        grade: grade.trim() || "N/A",
        status: "Completed",
      };
      setEducation((prev) => [...prev, newItem]);
      Alert.alert("Added 🎉", "New qualification added successfully.");
    }

    setModalVisible(false);
  };

  const EducationCard = ({ item }) => (
    <View style={styles.card}>
      <View style={styles.topRow}>
        <View style={styles.iconContainer}>
          <Ionicons name="school-outline" size={24} color="#173B8C" />
        </View>

        <TouchableOpacity style={styles.editButton} onPress={() => handleOpenEdit(item)}>
          <Ionicons name="create-outline" size={18} color="#173B8C" />
        </TouchableOpacity>
      </View>

      <Text style={styles.degree}>{item.degree}</Text>
      <Text style={styles.specialization}>{item.specialization}</Text>
      <Text style={styles.institution}>{item.institution}</Text>

      <View style={styles.infoRow}>
        <Ionicons name="calendar-outline" size={16} color="#64748B" />
        <Text style={styles.infoText}>{item.duration}</Text>
      </View>

      <View style={styles.infoRow}>
        <Ionicons name="ribbon-outline" size={16} color="#64748B" />
        <Text style={styles.infoText}>{item.grade}</Text>
      </View>

      <View style={styles.badge}>
        <Text style={styles.badgeText}>{item.status}</Text>
      </View>
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <ProfileHeader title="Education" showBack />

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        {/* Summary Card */}
        <View style={styles.summaryCard}>
          <View style={styles.summaryIcon}>
            <Ionicons name="school" size={32} color="#173B8C" />
          </View>

          <View style={{ flex: 1, marginLeft: 16 }}>
            <Text style={styles.summaryTitle}>Educational Details</Text>
            <Text style={styles.summarySubtitle}>
              {education.length} Qualification{education.length !== 1 ? "s" : ""} Listed
            </Text>
          </View>

          <TouchableOpacity style={styles.addButton} onPress={handleOpenAdd}>
            <Ionicons name="add" size={24} color="#173B8C" />
          </TouchableOpacity>
        </View>

        <Text style={styles.sectionTitle}>Academic Qualifications</Text>

        {education.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="school-outline" size={48} color="#94A3B8" />
            <Text style={styles.emptyTitle}>No Qualifications Added</Text>
            <Text style={styles.emptySubtitle}>Tap the + button above to add your academic qualifications.</Text>
          </View>
        ) : (
          education.map((item) => <EducationCard key={item.id} item={item} />)
        )}

        <SaveButton
          title="Save Changes"
          onPress={() => Alert.alert("Saved 🎉", "Educational details saved successfully.")}
        />

        <View style={{ height: 40 }} />
      </ScrollView>

      {/* Add / Edit Qualification Modal */}
      <Modal visible={modalVisible} transparent animationType="slide" onRequestClose={() => setModalVisible(false)}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>
                {editingItem ? "Edit Qualification" : "Add Qualification"}
              </Text>
              <TouchableOpacity onPress={() => setModalVisible(false)}>
                <Ionicons name="close-circle" size={24} color="#64748B" />
              </TouchableOpacity>
            </View>

            <Text style={styles.inputLabel}>DEGREE / CERTIFICATE</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. B.Tech / M.Sc / High School"
              value={degree}
              onChangeText={setDegree}
            />

            <Text style={styles.inputLabel}>FIELD / SPECIALIZATION</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. Computer Science"
              value={specialization}
              onChangeText={setSpecialization}
            />

            <Text style={styles.inputLabel}>INSTITUTION / UNIVERSITY</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. National Institute of Tech"
              value={institution}
              onChangeText={setInstitution}
            />

            <Text style={styles.inputLabel}>DURATION</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. 2018 - 2022"
              value={duration}
              onChangeText={setDuration}
            />

            <Text style={styles.inputLabel}>GRADE / PERCENTAGE / CGPA</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. 8.5 CGPA or 85%"
              value={grade}
              onChangeText={setGrade}
            />

            <TouchableOpacity style={styles.saveModalBtn} onPress={handleSave}>
              <Text style={styles.saveModalBtnText}>
                {editingItem ? "Update Qualification" : "Add Qualification"}
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F8FAFC" },
  content: { paddingHorizontal: 18, paddingBottom: 120 },
  summaryCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    padding: 18,
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#E8EDF3",
    marginBottom: 24,
    shadowColor: "#0F172A",
    shadowOpacity: 0.04,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 5 },
    elevation: 2,
  },
  summaryIcon: {
    width: 68,
    height: 68,
    borderRadius: 34,
    backgroundColor: "#EEF4FF",
    justifyContent: "center",
    alignItems: "center",
  },
  summaryTitle: { fontSize: 16, fontWeight: "800", color: "#0F172A" },
  summarySubtitle: { marginTop: 5, fontSize: 12, color: "#64748B", fontWeight: "600" },
  addButton: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: "#F8FAFC",
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  sectionTitle: { fontSize: 14, fontWeight: "800", color: "#0F172A", marginBottom: 14 },
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 18,
    padding: 18,
    marginBottom: 18,
    borderWidth: 1,
    borderColor: "#E8EDF3",
    shadowColor: "#0F172A",
    shadowOpacity: 0.04,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    elevation: 2,
  },
  topRow: { flexDirection: "row", justifyContent: "space-between", marginBottom: 14 },
  iconContainer: {
    width: 52,
    height: 52,
    borderRadius: 14,
    backgroundColor: "#EEF4FF",
    justifyContent: "center",
    alignItems: "center",
  },
  editButton: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: "#F8FAFC",
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  degree: { fontSize: 14, fontWeight: "800", color: "#0F172A" },
  specialization: { marginTop: 4, fontSize: 13, color: "#173B8C", fontWeight: "700" },
  institution: { marginTop: 6, fontSize: 14, color: "#475569", marginBottom: 12 },
  infoRow: { flexDirection: "row", alignItems: "center", marginBottom: 8 },
  infoText: { marginLeft: 8, fontSize: 14, color: "#64748B", fontWeight: "500" },
  badge: {
    alignSelf: "flex-start",
    marginTop: 14,
    backgroundColor: "#DCFCE7",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
  },
  badgeText: { color: "#15803D", fontSize: 12, fontWeight: "700" },
  emptyState: {
    backgroundColor: "#FFFFFF",
    borderRadius: 18,
    padding: 32,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    marginBottom: 20,
  },
  emptyTitle: { fontSize: 15, fontWeight: "800", color: "#0F172A", marginTop: 12 },
  emptySubtitle: { fontSize: 13, color: "#64748B", textAlign: "center", marginTop: 6 },
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