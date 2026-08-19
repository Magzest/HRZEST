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

export default function EmergencyContactScreen() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [modalVisible, setModalVisible] = useState(false);

  const [emergency, setEmergency] = useState({
    primaryName: user?.emergency_contact_name || "Not Provided",
    primaryRelation: user?.emergency_contact_relation || "Not Provided",
    primaryPhone: user?.emergency_contact_phone || "Not Provided",
    address: user?.address || "Not Provided",
  });

  const [editName, setEditName] = useState(emergency.primaryName);
  const [editRelation, setEditRelation] = useState(emergency.primaryRelation);
  const [editPhone, setEditPhone] = useState(emergency.primaryPhone);
  const [editAddress, setEditAddress] = useState(emergency.address);

  useEffect(() => {
    fetchEmployeeProfile()
      .then((res) => {
        if (res?.data?.ok && res?.data?.profile) {
          const p = res.data.profile;
          const updated = {
            primaryName: p.emergency_contact_name || user?.emergency_contact_name || "Not Provided",
            primaryRelation: p.emergency_contact_relation || user?.emergency_contact_relation || "Not Provided",
            primaryPhone: p.emergency_contact_phone || user?.emergency_contact_phone || "Not Provided",
            address: p.address || user?.address || "Not Provided",
          };
          setEmergency(updated);
          setEditName(updated.primaryName);
          setEditRelation(updated.primaryRelation);
          setEditPhone(updated.primaryPhone);
          setEditAddress(updated.address);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSave = () => {
    // No Bearer-token-compatible endpoint exists to update emergency
    // contact details from mobile yet -- only a session-based web route
    // does this.
    Alert.alert(
      "Not Available on Mobile Yet",
      "Updating emergency contact details is only available from the web employee portal for now."
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <ProfileHeader title="Emergency Contact" showBack />

      {loading ? (
        <View style={{ flex: 1, justifyContent: "center", alignItems: "center" }}>
          <ActivityIndicator size="large" color="#173B8C" />
        </View>
      ) : (
        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
          {/* Summary Card */}
          <View style={styles.summaryCard}>
            <View style={styles.avatar}>
              <Ionicons name="medical" size={24} color="#FFFFFF" />
            </View>

            <View style={styles.summaryText}>
              <Text style={styles.name}>{emergency.primaryName}</Text>
              <Text style={styles.subText}>{emergency.primaryRelation} • {emergency.primaryPhone}</Text>
            </View>

            <TouchableOpacity style={styles.editBtn} onPress={() => setModalVisible(true)}>
              <Ionicons name="create-outline" size={20} color="#173B8C" />
            </TouchableOpacity>
          </View>

          {/* Details */}
          <DetailCard icon="person-outline" label="Contact Name" value={emergency.primaryName} />
          <DetailCard icon="people-outline" label="Relationship" value={emergency.primaryRelation} />
          <DetailCard icon="call-outline" label="Phone Number" value={emergency.primaryPhone} />
          <DetailCard icon="location-outline" label="Family Address" value={emergency.address} />
        </ScrollView>
      )}

      {/* Edit Emergency Contact Modal */}
      <Modal visible={modalVisible} transparent animationType="slide" onRequestClose={() => setModalVisible(false)}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Edit Emergency Contact</Text>
              <TouchableOpacity onPress={() => setModalVisible(false)}>
                <Ionicons name="close-circle" size={24} color="#64748B" />
              </TouchableOpacity>
            </View>

            <Text style={styles.inputLabel}>CONTACT NAME</Text>
            <TextInput style={styles.input} value={editName} onChangeText={setEditName} placeholder="Family member name" />

            <Text style={styles.inputLabel}>RELATIONSHIP</Text>
            <TextInput style={styles.input} value={editRelation} onChangeText={setEditRelation} placeholder="Parent / Spouse / Sibling" />

            <Text style={styles.inputLabel}>PHONE NUMBER</Text>
            <TextInput style={styles.input} value={editPhone} onChangeText={setEditPhone} keyboardType="phone-pad" />

            <Text style={styles.inputLabel}>FAMILY ADDRESS</Text>
            <TextInput style={styles.input} value={editAddress} onChangeText={setEditAddress} multiline />

            <TouchableOpacity style={styles.saveModalBtn} onPress={handleSave}>
              <Text style={styles.saveModalBtnText}>Save Emergency Contact</Text>
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
    backgroundColor: "#EF4444",
    justifyContent: "center",
    alignItems: "center",
    marginRight: 14,
  },
  summaryText: { flex: 1 },
  name: { fontSize: 16, fontWeight: "800", color: "#0F172A" },
  subText: { fontSize: 13, fontWeight: "600", color: "#64748B", marginTop: 2 },
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