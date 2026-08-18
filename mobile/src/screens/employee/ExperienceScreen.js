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

export default function ExperienceScreen() {
  const [experiences, setExperiences] = useState([
    {
      id: "1",
      designation: "Software Engineer",
      company: "Acme Tech Solutions",
      duration: "2022 - Present",
      location: "Bengaluru, India",
      employmentType: "Full-Time",
      description: "Developing scalable full-stack web and mobile applications.",
    },
  ]);

  const [modalVisible, setModalVisible] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const [designation, setDesignation] = useState("");
  const [company, setCompany] = useState("");
  const [duration, setDuration] = useState("");
  const [location, setLocation] = useState("");
  const [description, setDescription] = useState("");

  const handleOpenAdd = () => {
    setEditingItem(null);
    setDesignation("");
    setCompany("");
    setDuration("");
    setLocation("");
    setDescription("");
    setModalVisible(true);
  };

  const handleOpenEdit = (item) => {
    setEditingItem(item);
    setDesignation(item.designation);
    setCompany(item.company);
    setDuration(item.duration);
    setLocation(item.location);
    setDescription(item.description);
    setModalVisible(true);
  };

  const handleSave = () => {
    if (!designation.trim() || !company.trim()) {
      Alert.alert("Input Required", "Designation and Company Name are required fields.");
      return;
    }

    if (editingItem) {
      setExperiences((prev) =>
        prev.map((e) =>
          e.id === editingItem.id
            ? {
                ...e,
                designation: designation.trim(),
                company: company.trim(),
                duration: duration.trim(),
                location: location.trim(),
                description: description.trim(),
              }
            : e
        )
      );
      Alert.alert("Updated 🎉", "Experience details updated successfully.");
    } else {
      const newItem = {
        id: Date.now().toString(),
        designation: designation.trim(),
        company: company.trim(),
        duration: duration.trim() || "Present",
        location: location.trim() || "Remote",
        employmentType: "Full-Time",
        description: description.trim() || "Worked on core projects.",
      };
      setExperiences((prev) => [...prev, newItem]);
      Alert.alert("Added 🎉", "New experience record added successfully.");
    }

    setModalVisible(false);
  };

  const ExperienceCard = ({ item }) => (
    <View style={styles.card}>
      <View style={styles.topRow}>
        <View style={styles.iconContainer}>
          <Ionicons name="briefcase-outline" size={24} color="#173B8C" />
        </View>

        <TouchableOpacity style={styles.editButton} onPress={() => handleOpenEdit(item)}>
          <Ionicons name="create-outline" size={18} color="#173B8C" />
        </TouchableOpacity>
      </View>

      <Text style={styles.designation}>{item.designation}</Text>
      <Text style={styles.company}>{item.company}</Text>

      <View style={styles.infoRow}>
        <Ionicons name="calendar-outline" size={16} color="#64748B" />
        <Text style={styles.infoText}>{item.duration}</Text>
      </View>

      <View style={styles.infoRow}>
        <Ionicons name="location-outline" size={16} color="#64748B" />
        <Text style={styles.infoText}>{item.location}</Text>
      </View>

      <View style={styles.badge}>
        <Text style={styles.badgeText}>{item.employmentType}</Text>
      </View>

      <Text style={styles.description}>{item.description}</Text>
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <ProfileHeader title="Experience" showBack />

      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        {/* Summary Card */}
        <View style={styles.summaryCard}>
          <View style={styles.summaryIcon}>
            <Ionicons name="briefcase" size={32} color="#173B8C" />
          </View>

          <View style={{ flex: 1, marginLeft: 16 }}>
            <Text style={styles.summaryTitle}>Professional Experience</Text>
            <Text style={styles.summarySubtitle}>
              Total Experience: {experiences.length} Position{experiences.length !== 1 ? "s" : ""}
            </Text>
          </View>

          <TouchableOpacity style={styles.addButton} onPress={handleOpenAdd}>
            <Ionicons name="add" size={24} color="#173B8C" />
          </TouchableOpacity>
        </View>

        <Text style={styles.sectionTitle}>Employment History</Text>

        {experiences.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="briefcase-outline" size={48} color="#94A3B8" />
            <Text style={styles.emptyTitle}>No Experience Added</Text>
            <Text style={styles.emptySubtitle}>Tap the + button above to add past employment history.</Text>
          </View>
        ) : (
          experiences.map((item) => <ExperienceCard key={item.id} item={item} />)
        )}

        <SaveButton
          title="Save Changes"
          onPress={() => Alert.alert("Saved 🎉", "Experience details saved successfully.")}
        />

        <View style={{ height: 40 }} />
      </ScrollView>

      {/* Add / Edit Experience Modal */}
      <Modal visible={modalVisible} transparent animationType="slide" onRequestClose={() => setModalVisible(false)}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>
                {editingItem ? "Edit Experience" : "Add Experience"}
              </Text>
              <TouchableOpacity onPress={() => setModalVisible(false)}>
                <Ionicons name="close-circle" size={24} color="#64748B" />
              </TouchableOpacity>
            </View>

            <Text style={styles.inputLabel}>DESIGNATION / ROLE</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. Senior Software Engineer"
              value={designation}
              onChangeText={setDesignation}
            />

            <Text style={styles.inputLabel}>COMPANY NAME</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. Acme Corporation"
              value={company}
              onChangeText={setCompany}
            />

            <Text style={styles.inputLabel}>DURATION</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. Jan 2021 - Dec 2023"
              value={duration}
              onChangeText={setDuration}
            />

            <Text style={styles.inputLabel}>LOCATION</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. Mumbai, India"
              value={location}
              onChangeText={setLocation}
            />

            <Text style={styles.inputLabel}>DESCRIPTION / RESPONSIBILITIES</Text>
            <TextInput
              style={[styles.input, { height: 70, textAlignVertical: "top" }]}
              placeholder="Key contributions and achievements..."
              multiline
              value={description}
              onChangeText={setDescription}
            />

            <TouchableOpacity style={styles.saveModalBtn} onPress={handleSave}>
              <Text style={styles.saveModalBtnText}>
                {editingItem ? "Update Experience" : "Add Experience"}
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
    marginBottom: 24,
    borderWidth: 1,
    borderColor: "#E8EDF3",
    flexDirection: "row",
    alignItems: "center",
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
  designation: { fontSize: 14, fontWeight: "800", color: "#0F172A" },
  company: { fontSize: 13, color: "#173B8C", fontWeight: "700", marginTop: 4, marginBottom: 12 },
  infoRow: { flexDirection: "row", alignItems: "center", marginBottom: 8 },
  infoText: { marginLeft: 8, fontSize: 14, color: "#64748B", fontWeight: "500" },
  badge: {
    alignSelf: "flex-start",
    backgroundColor: "#DCFCE7",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    marginVertical: 14,
  },
  badgeText: { color: "#15803D", fontWeight: "700", fontSize: 12 },
  description: { fontSize: 14, color: "#475569", lineHeight: 22 },
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