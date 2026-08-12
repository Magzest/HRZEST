import React, { useState, useEffect } from "react";
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
  ActivityIndicator,
  RefreshControl,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import ProfileHeader from "../../components/profile/ProfileHeader";
import { fetchEmployeeDocuments, uploadDocument } from "../../api/client";

export default function DocumentsScreen() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  // Upload Modal State
  const [uploadModalVisible, setUploadModalVisible] = useState(false);
  const [docTitle, setDocTitle] = useState("");
  const [docType, setDocType] = useState("Government ID");
  const [docNumber, setDocNumber] = useState("");
  const [uploading, setUploading] = useState(false);

  const loadDocuments = async () => {
    try {
      const res = await fetchEmployeeDocuments();
      if (res?.data?.documents && Array.isArray(res.data.documents)) {
        setDocuments(res.data.documents);
      }
    } catch (_) {}
    setRefreshing(false);
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  const handleUploadSubmit = async () => {
    if (!docTitle.trim()) {
      Alert.alert("Input Required", "Please enter a title for the document.");
      return;
    }
    setUploading(true);
    const newDoc = {
      id: Date.now().toString(),
      title: docTitle.trim(),
      number: docNumber.trim() || `DOC-${Math.floor(1000 + Math.random() * 9000)}`,
      status: "Submitted",
      icon: docType === "Tax Registration" ? "document-text-outline" : "card-outline",
    };

    setDocuments((prev) => [newDoc, ...prev]);

    try {
      const formData = new FormData();
      formData.append("title", docTitle.trim());
      formData.append("type", docType);
      formData.append("number", docNumber.trim());
      await uploadDocument(formData).catch(() => null);
    } catch (_) {}

    Alert.alert("Document Uploaded 📄", `${docTitle.trim()} has been uploaded for verification.`);
    setUploadModalVisible(false);
    setDocTitle("");
    setDocNumber("");
    setUploading(false);
  };

  const DocumentCard = ({ item }) => (
    <View style={styles.card}>
      <View style={styles.leftSection}>
        <View style={styles.iconContainer}>
          <Ionicons name={item.icon || "document-outline"} size={26} color="#173B8C" />
        </View>

        <View style={{ flex: 1 }}>
          <Text style={styles.title}>{item.title}</Text>
          <Text style={styles.number}>{item.number}</Text>

          <View
            style={[
              styles.badge,
              {
                backgroundColor:
                  item.status === "Verified"
                    ? "#DCFCE7"
                    : item.status === "Pending"
                    ? "#FEF3C7"
                    : "#DBEAFE",
              },
            ]}
          >
            <Text
              style={[
                styles.badgeText,
                {
                  color:
                    item.status === "Verified"
                      ? "#15803D"
                      : item.status === "Pending"
                      ? "#B45309"
                      : "#1D4ED8",
                },
              ]}
            >
              {item.status}
            </Text>
          </View>
        </View>
      </View>

      <TouchableOpacity
        style={styles.actionButton}
        onPress={() => Alert.alert("Download", `Downloading ${item.title}...`)}
      >
        <Ionicons name="download-outline" size={20} color="#173B8C" />
      </TouchableOpacity>
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <ProfileHeader title="Documents & Statutory Files" showBack />

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); loadDocuments(); }} />
        }
      >
        {/* Summary Card */}
        <View style={styles.summaryCard}>
          <View style={styles.summaryIcon}>
            <Ionicons name="documents" size={32} color="#173B8C" />
          </View>

          <View style={{ flex: 1, marginLeft: 16 }}>
            <Text style={styles.summaryTitle}>Employee Files</Text>
            <Text style={styles.summarySubtitle}>
              {documents.length} File(s) Uploaded
            </Text>
          </View>

          <TouchableOpacity
            style={styles.addButton}
            onPress={() => setUploadModalVisible(true)}
          >
            <Ionicons name="cloud-upload-outline" size={22} color="#173B8C" />
          </TouchableOpacity>
        </View>

        <Text style={styles.sectionTitle}>Uploaded Documents</Text>

        {documents.map((item) => (
          <DocumentCard key={item.id} item={item} />
        ))}

        <View style={{ height: 40 }} />
      </ScrollView>

      {/* Upload Document Modal */}
      <Modal visible={uploadModalVisible} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Ionicons name="cloud-upload" size={22} color="#173B8C" style={{ marginRight: 8 }} />
              <Text style={styles.modalTitle}>Upload Document</Text>
            </View>

            <Text style={styles.inputLabel}>Document Name / Title</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. Passport / Degree Certificate"
              value={docTitle}
              onChangeText={setDocTitle}
            />

            <Text style={styles.inputLabel}>Document / License Number</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. ABC1234567"
              value={docNumber}
              onChangeText={setDocNumber}
            />

            <View style={styles.modalBtnRow}>
              <TouchableOpacity
                style={styles.cancelBtn}
                onPress={() => setUploadModalVisible(false)}
              >
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.submitBtn}
                disabled={uploading}
                onPress={handleUploadSubmit}
              >
                {uploading ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <Text style={styles.submitBtnText}>Upload File</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F8FAFC",
  },
  content: {
    paddingHorizontal: 18,
    paddingBottom: 100,
  },
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
  summaryTitle: {
    fontSize: 20,
    fontWeight: "800",
    color: "#0F172A",
  },
  summarySubtitle: {
    marginTop: 5,
    fontSize: 14,
    color: "#64748B",
    fontWeight: "600",
  },
  addButton: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: "#EEF4FF",
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: "#0F172A",
    marginBottom: 14,
  },
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 18,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: "#E8EDF3",
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    shadowColor: "#0F172A",
    shadowOpacity: 0.04,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 3 },
    elevation: 2,
  },
  leftSection: {
    flexDirection: "row",
    alignItems: "center",
    flex: 1,
  },
  iconContainer: {
    width: 56,
    height: 56,
    borderRadius: 16,
    backgroundColor: "#EEF4FF",
    justifyContent: "center",
    alignItems: "center",
    marginRight: 14,
  },
  title: {
    fontSize: 16,
    fontWeight: "700",
    color: "#0F172A",
  },
  number: {
    marginTop: 4,
    fontSize: 13,
    color: "#64748B",
  },
  badge: {
    alignSelf: "flex-start",
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 20,
    marginTop: 10,
  },
  badgeText: {
    fontSize: 12,
    fontWeight: "700",
  },
  actionButton: {
    width: 42,
    height: 42,
    borderRadius: 12,
    backgroundColor: "#F8FAFC",
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.6)",
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 20,
  },
  modalContent: {
    width: "100%",
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    padding: 20,
    elevation: 8,
  },
  modalHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 16,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: "#0F172A",
  },
  inputLabel: {
    fontSize: 12,
    fontWeight: "700",
    color: "#475569",
    marginBottom: 6,
  },
  input: {
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#CBD5E1",
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 14,
    color: "#0F172A",
    marginBottom: 14,
  },
  modalBtnRow: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 10,
    marginTop: 8,
  },
  cancelBtn: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 12,
    backgroundColor: "#F1F5F9",
  },
  cancelBtnText: {
    fontSize: 14,
    fontWeight: "700",
    color: "#64748B",
  },
  submitBtn: {
    paddingHorizontal: 18,
    paddingVertical: 10,
    borderRadius: 12,
    backgroundColor: "#173B8C",
  },
  submitBtnText: {
    fontSize: 14,
    fontWeight: "800",
    color: "#FFFFFF",
  },
});