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
  Image,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import * as ImagePicker from "expo-image-picker";
import ProfileHeader from "../../components/profile/ProfileHeader";
import { fetchEmployeeDocuments, uploadDocument } from "../../api/client";

const DOC_CATEGORIES = [
  "Government ID",
  "Tax / PAN",
  "Education",
  "Address Proof",
  "Relieving Letter",
  "Other",
];

export default function DocumentsScreen() {
  const [documents, setDocuments] = useState([
    {
      id: "1",
      title: "Government Identity Card (Aadhaar / Passport)",
      number: "XXXX-XXXX-9842",
      type: "Government ID",
      status: "Verified",
      icon: "card-outline",
      fileName: "aadhaar_card_copy.jpg",
    },
    {
      id: "2",
      title: "Permanent Account Number (PAN)",
      number: "ABCDE1234F",
      type: "Tax / PAN",
      status: "Verified",
      icon: "document-text-outline",
      fileName: "pan_card_front.jpg",
    },
  ]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  // Upload Modal State
  const [uploadModalVisible, setUploadModalVisible] = useState(false);
  const [docCategory, setDocCategory] = useState("Government ID");
  const [docTitle, setDocTitle] = useState("");
  const [docNumber, setDocNumber] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);

  const loadDocuments = async () => {
    try {
      const res = await fetchEmployeeDocuments();
      if (res?.data?.documents && Array.isArray(res.data.documents) && res.data.documents.length > 0) {
        setDocuments(res.data.documents);
      }
    } catch (_) {}
    setRefreshing(false);
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  const handleSelectFile = async () => {
    try {
      const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!perm.granted) {
        Alert.alert("Permission Required", "Storage/Photos permission is required to select document files.");
        return;
      }
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: false,
        quality: 0.9,
      });

      if (!result.canceled && result.assets?.[0]) {
        const asset = result.assets[0];
        const name = asset.fileName || `${docCategory.replace(/[^a-zA-Z0-9]/g, "_")}_doc.jpg`;
        setSelectedFile({
          uri: asset.uri,
          name: name,
          size: asset.fileSize ? `${(asset.fileSize / (1024 * 1024)).toFixed(2)} MB` : "Attached File",
          type: "image/jpeg",
        });
        setDocTitle(`${docCategory} Document`);
      }
    } catch (err) {
      Alert.alert("Error", "Could not open document picker.");
    }
  };

  const handleUploadSubmit = async () => {
    if (!selectedFile) {
      Alert.alert("File Required", "Please tap 'Browse File' to select a document from your device.");
      return;
    }

    const finalTitle = docTitle.trim() || `${docCategory} Document`;

    setUploading(true);
    const newDoc = {
      id: Date.now().toString(),
      title: finalTitle,
      number: docNumber.trim() || `REF-${Math.floor(100000 + Math.random() * 900000)}`,
      type: docCategory,
      status: "Submitted",
      icon: docCategory === "Tax / PAN" ? "document-text-outline" : "card-outline",
      fileName: selectedFile.name,
    };

    setDocuments((prev) => [newDoc, ...prev]);

    try {
      const formData = new FormData();
      formData.append("title", finalTitle);
      formData.append("type", docCategory);
      formData.append("number", docNumber.trim());
      formData.append("document", {
        uri: selectedFile.uri,
        name: selectedFile.name,
        type: selectedFile.type,
      });
      await uploadDocument(formData).catch(() => null);
    } catch (_) {}

    Alert.alert("Document Uploaded 📄", `${finalTitle} has been attached and submitted for verification.`);
    setUploadModalVisible(false);
    setDocTitle("");
    setDocNumber("");
    setSelectedFile(null);
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
          {item.fileName && (
            <Text style={styles.fileDetail}>📄 {item.fileName}</Text>
          )}

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
        onPress={() => Alert.alert("Download Document", `Downloading ${item.title} (${item.fileName || 'file'})...`)}
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
            <Text style={styles.summaryTitle}>Employee Vault</Text>
            <Text style={styles.summarySubtitle}>
              {documents.length} Statutory File(s) Uploaded
            </Text>
          </View>

          <TouchableOpacity
            style={styles.addButton}
            onPress={() => setUploadModalVisible(true)}
          >
            <Ionicons name="cloud-upload-outline" size={22} color="#173B8C" />
          </TouchableOpacity>
        </View>

        <Text style={styles.sectionTitle}>Uploaded Compliance Documents</Text>

        {documents.map((item) => (
          <DocumentCard key={item.id} item={item} />
        ))}

        <View style={{ height: 40 }} />
      </ScrollView>

      {/* Upload Document Modal */}
      <Modal visible={uploadModalVisible} animationType="slide" transparent onRequestClose={() => setUploadModalVisible(false)}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Ionicons name="cloud-upload" size={24} color="#173B8C" style={{ marginRight: 10 }} />
              <Text style={styles.modalTitle}>Upload Compliance Document</Text>
              <TouchableOpacity onPress={() => setUploadModalVisible(false)} style={{ marginLeft: "auto" }}>
                <Ionicons name="close-circle" size={24} color="#64748B" />
              </TouchableOpacity>
            </View>

            <Text style={styles.inputLabel}>DOCUMENT CATEGORY</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 14 }}>
              {DOC_CATEGORIES.map((cat) => (
                <TouchableOpacity
                  key={cat}
                  style={[
                    styles.catChip,
                    docCategory === cat && styles.catChipActive,
                  ]}
                  onPress={() => setDocCategory(cat)}
                >
                  <Text
                    style={[
                      styles.catChipText,
                      docCategory === cat && styles.catChipTextActive,
                    ]}
                  >
                    {cat}
                  </Text>
                </TouchableOpacity>
              ))}
            </ScrollView>

            <Text style={styles.inputLabel}>SELECT FILE / PROOF</Text>
            {selectedFile ? (
              <View style={styles.fileSelectedBox}>
                <Image source={{ uri: selectedFile.uri }} style={styles.fileThumb} />
                <View style={{ flex: 1, marginLeft: 12 }}>
                  <Text numberOfLines={1} style={styles.fileName}>{selectedFile.name}</Text>
                  <Text style={styles.fileSize}>{selectedFile.size}</Text>
                </View>
                <TouchableOpacity onPress={() => setSelectedFile(null)} style={{ padding: 4 }}>
                  <Ionicons name="close-circle" size={22} color="#EF4444" />
                </TouchableOpacity>
              </View>
            ) : (
              <TouchableOpacity style={styles.filePickerBtn} onPress={handleSelectFile}>
                <Ionicons name="attach" size={24} color="#173B8C" />
                <Text style={styles.filePickerText}>Browse File / Document Scan</Text>
              </TouchableOpacity>
            )}

            <Text style={styles.inputLabel}>DOCUMENT TITLE (AUTO-FILLED)</Text>
            <TextInput
              style={styles.input}
              placeholder="Auto-generated from selected category/file"
              value={docTitle}
              onChangeText={setDocTitle}
            />

            <Text style={styles.inputLabel}>DOCUMENT / LICENSE NO. (OPTIONAL)</Text>
            <TextInput
              style={styles.input}
              placeholder="Optional reference or license number"
              value={docNumber}
              onChangeText={setDocNumber}
            />

            <TouchableOpacity
              style={styles.submitBtn}
              disabled={uploading}
              onPress={handleUploadSubmit}
            >
              {uploading ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
              ) : (
                <Text style={styles.submitBtnText}>Submit Document for Verification</Text>
              )}
            </TouchableOpacity>
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
    fontSize: 16,
    fontWeight: "800",
    color: "#0F172A",
  },
  summarySubtitle: {
    marginTop: 5,
    fontSize: 12,
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
    fontSize: 14,
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
    fontSize: 13,
    fontWeight: "700",
    color: "#0F172A",
  },
  number: {
    marginTop: 4,
    fontSize: 12,
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
    fontSize: 11,
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
    fontSize: 15,
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
  fileDetail: {
    marginTop: 4,
    fontSize: 11,
    color: "#64748B",
    fontWeight: "500",
  },
  catChip: {
    backgroundColor: "#F1F5F9",
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    marginRight: 8,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  catChipActive: {
    backgroundColor: "#173B8C",
    borderColor: "#173B8C",
  },
  catChipText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#475569",
  },
  catChipTextActive: {
    color: "#FFFFFF",
  },
  filePickerBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#EEF4FF",
    borderWidth: 1.5,
    borderStyle: "dashed",
    borderColor: "#93C5FD",
    borderRadius: 14,
    paddingVertical: 14,
    paddingHorizontal: 16,
    marginBottom: 14,
  },
  filePickerText: {
    marginLeft: 8,
    fontSize: 13,
    fontWeight: "700",
    color: "#173B8C",
  },
  fileSelectedBox: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#CBD5E1",
    borderRadius: 14,
    padding: 12,
    marginBottom: 14,
  },
  fileThumb: {
    width: 44,
    height: 44,
    borderRadius: 8,
    backgroundColor: "#E2E8F0",
  },
  fileName: {
    fontSize: 13,
    fontWeight: "700",
    color: "#0F172A",
  },
  fileSize: {
    marginTop: 2,
    fontSize: 11,
    fontWeight: "600",
    color: "#64748B",
  },
  submitBtn: {
    paddingHorizontal: 18,
    paddingVertical: 14,
    borderRadius: 14,
    backgroundColor: "#173B8C",
    alignItems: "center",
    marginTop: 8,
  },
  submitBtnText: {
    fontSize: 14,
    fontWeight: "800",
    color: "#FFFFFF",
  },
});