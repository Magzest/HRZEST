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

export default function BankDetailsScreen() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [modalVisible, setModalVisible] = useState(false);

  const [bankInfo, setBankInfo] = useState({
    accountName: user?.name || "",
    bankName: user?.bank_name || "Not Provided",
    accountNumber: user?.bank_account || "Not Provided",
    ifscCode: user?.bank_ifsc || "Not Provided",
    panNumber: user?.pan_number || "Not Provided",
    aadharNumber: user?.aadhar_number || "Not Provided",
  });

  const [editBankName, setEditBankName] = useState(bankInfo.bankName);
  const [editAccountName, setEditAccountName] = useState(bankInfo.accountName);
  const [editAccountNumber, setEditAccountNumber] = useState(bankInfo.accountNumber);
  const [editIfscCode, setEditIfscCode] = useState(bankInfo.ifscCode);
  const [editPanNumber, setEditPanNumber] = useState(bankInfo.panNumber);
  const [editAadharNumber, setEditAadharNumber] = useState(bankInfo.aadharNumber);

  useEffect(() => {
    fetchEmployeeProfile()
      .then((res) => {
        if (res?.data?.ok && res?.data?.profile) {
          const p = res.data.profile;
          const updated = {
            accountName: p.name || user?.name || "",
            bankName: p.bank_name || user?.bank_name || "Not Provided",
            accountNumber: p.bank_account || user?.bank_account || "Not Provided",
            ifscCode: p.bank_ifsc || user?.bank_ifsc || "Not Provided",
            panNumber: p.pan_number || user?.pan_number || "Not Provided",
            aadharNumber: p.aadhar_number || user?.aadhar_number || "Not Provided",
          };
          setBankInfo(updated);
          setEditBankName(updated.bankName);
          setEditAccountName(updated.accountName);
          setEditAccountNumber(updated.accountNumber);
          setEditIfscCode(updated.ifscCode);
          setEditPanNumber(updated.panNumber);
          setEditAadharNumber(updated.aadharNumber);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSave = () => {
    setBankInfo((prev) => ({
      ...prev,
      bankName: editBankName.trim() || "Not Provided",
      accountName: editAccountName.trim() || "",
      accountNumber: editAccountNumber.trim() || "Not Provided",
      ifscCode: editIfscCode.trim() || "Not Provided",
      panNumber: editPanNumber.trim() || "Not Provided",
      aadharNumber: editAadharNumber.trim() || "Not Provided",
    }));

    Alert.alert("Updated 🎉", "Bank and identity details updated successfully.");
    setModalVisible(false);
  };

  return (
    <SafeAreaView style={styles.container}>
      <ProfileHeader title="Bank Details" showBack />

      {loading ? (
        <View style={{ flex: 1, justifyContent: "center", alignItems: "center" }}>
          <ActivityIndicator size="large" color="#173B8C" />
        </View>
      ) : (
        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
          {/* Summary Card */}
          <View style={styles.summaryCard}>
            <View style={styles.avatar}>
              <Ionicons name="card" size={24} color="#FFFFFF" />
            </View>

            <View style={styles.summaryText}>
              <Text style={styles.name}>{bankInfo.bankName}</Text>
              <Text style={styles.subText}>{bankInfo.accountName}</Text>
            </View>

            <TouchableOpacity style={styles.editBtn} onPress={() => setModalVisible(true)}>
              <Ionicons name="create-outline" size={20} color="#173B8C" />
            </TouchableOpacity>
          </View>

          {/* Details */}
          <DetailCard icon="business-outline" label="Bank Name" value={bankInfo.bankName} />
          <DetailCard icon="person-outline" label="Account Holder" value={bankInfo.accountName} />
          <DetailCard icon="card-outline" label="Account Number" value={bankInfo.accountNumber} />
          <DetailCard icon="qr-code-outline" label="IFSC Code" value={bankInfo.ifscCode} />
          <DetailCard icon="document-text-outline" label="PAN Number" value={bankInfo.panNumber} />
          <DetailCard icon="id-card-outline" label="Aadhar Number" value={bankInfo.aadharNumber} />
        </ScrollView>
      )}

      {/* Edit Bank Details Modal */}
      <Modal visible={modalVisible} transparent animationType="slide" onRequestClose={() => setModalVisible(false)}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Edit Bank & Identity Details</Text>
              <TouchableOpacity onPress={() => setModalVisible(false)}>
                <Ionicons name="close-circle" size={24} color="#64748B" />
              </TouchableOpacity>
            </View>

            <Text style={styles.inputLabel}>BANK NAME</Text>
            <TextInput style={styles.input} value={editBankName} onChangeText={setEditBankName} placeholder="e.g. HDFC Bank" />

            <Text style={styles.inputLabel}>ACCOUNT HOLDER NAME</Text>
            <TextInput style={styles.input} value={editAccountName} onChangeText={setEditAccountName} />

            <Text style={styles.inputLabel}>ACCOUNT NUMBER</Text>
            <TextInput style={styles.input} value={editAccountNumber} onChangeText={setEditAccountNumber} keyboardType="number-pad" />

            <Text style={styles.inputLabel}>IFSC CODE</Text>
            <TextInput style={styles.input} value={editIfscCode} onChangeText={setEditIfscCode} autoCapitalize="characters" />

            <Text style={styles.inputLabel}>PAN NUMBER</Text>
            <TextInput style={styles.input} value={editPanNumber} onChangeText={setEditPanNumber} autoCapitalize="characters" />

            <Text style={styles.inputLabel}>AADHAR NUMBER</Text>
            <TextInput style={styles.input} value={editAadharNumber} onChangeText={setEditAadharNumber} keyboardType="number-pad" />

            <TouchableOpacity style={styles.saveModalBtn} onPress={handleSave}>
              <Text style={styles.saveModalBtnText}>Save Bank Details</Text>
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
    backgroundColor: "#16A34A",
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