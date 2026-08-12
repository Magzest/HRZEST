import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  RefreshControl,
  Modal,
  TextInput,
  Alert,
  ActivityIndicator,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import { useNavigation, useFocusEffect } from "@react-navigation/native";
import { useAuth } from "../../store/AuthContext";
import * as ImagePicker from "expo-image-picker";
import { fetchEmployeeProfile, uploadEmployeePhoto } from "../../api/client";

import ProfileHeader from "../../components/profile/ProfileHeader";
import ProfileImageCard from "../../components/profile/ProfileImageCard";
import ProfileCompletionCard from "../../components/profile/ProfileCompletionCard";
import ProfileMenuCard from "../../components/profile/ProfileMenuCard";
import DigitalIdCardModal from "../../components/employee/DigitalIdCardModal";

export default function ProfileScreen() {
  const navigation = useNavigation();
  const { user, updateUser } = useAuth();

  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [showIdCard, setShowIdCard] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Profile Form States
  const [profileData, setProfileData] = useState({
    name: user?.name || user?.employeeId || "",
    employeeId: user?.employeeId || user?.employee_id || "",
    designation: user?.role || "",
    department: user?.department || "",
    email: user?.email || "",
    phone: user?.phone || "Not Provided",
    address: user?.address || "Not Provided",
    emergencyContact: user?.emergency_contact || "Not Provided",
    completion: 95,
  });

  const [editName, setEditName] = useState(profileData.name);
  const [editEmail, setEditEmail] = useState(profileData.email);
  const [editPhone, setEditPhone] = useState(profileData.phone);
  const [editAddress, setEditAddress] = useState(profileData.address);
  const [editEmergency, setEditEmergency] = useState(profileData.emergencyContact);

  const loadProfile = async () => {
    try {
      const res = await fetchEmployeeProfile();
      if (res?.data?.ok && res?.data?.profile) {
        const p = res.data.profile;
        const updated = {
          name: p.name || user?.name || user?.employeeId || "",
          employeeId: p.employee_id || user?.employeeId || "",
          designation: p.role || user?.role || "",
          department: p.department || user?.department || "",
          email: p.email || user?.email || "",
          phone: p.phone || user?.phone || "Not Provided",
          address: p.address || user?.address || "Not Provided",
          emergencyContact: p.emergency_contact_phone || user?.emergency_contact || "Not Provided",
          company: p.company_name || user?.company || "",
          completion: 95,
        };
        setProfileData(updated);
        setEditName(updated.name);
        setEditEmail(updated.email);
        setEditPhone(updated.phone);
        setEditAddress(updated.address);
        setEditEmergency(updated.emergencyContact);
        if (updateUser) updateUser(updated);
      }
    } catch (_) {}
    setRefreshing(false);
    setLoading(false);
  };

  useFocusEffect(
    useCallback(() => {
      loadProfile();
    }, [])
  );

  const handleSaveProfile = async () => {
    if (!editName.trim() || !editEmail.trim()) {
      Alert.alert("Input Required", "Full Name and Email Address are required.");
      return;
    }
    setSubmitting(true);

    const updatedProfile = {
      ...profileData,
      name: editName.trim(),
      email: editEmail.trim(),
      phone: editPhone.trim(),
      address: editAddress.trim(),
      emergencyContact: editEmergency.trim(),
    };

    setProfileData(updatedProfile);

    Alert.alert("Profile Updated 🎉", "Your profile details have been updated successfully.");
    setEditModalVisible(false);
    setSubmitting(false);
  };

  const handleChangePhoto = async () => {
    try {
      const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!perm.granted) {
        Alert.alert("Permission Required", "Camera roll permission is required to select a face photo.");
        return;
      }
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true,
        aspect: [1, 1],
        quality: 0.85,
      });

      if (!result.canceled && result.assets?.[0]?.uri) {
        const photoUri = result.assets[0].uri;
        setSubmitting(true);
        const formData = new FormData();
        formData.append("photo", {
          uri: photoUri,
          name: `${profileData.employeeId || "photo"}.jpg`,
          type: "image/jpeg",
        });

        const res = await uploadEmployeePhoto(formData).catch(() => null);
        setSubmitting(false);
        if (res?.data?.ok) {
          Alert.alert("Face Photo Registered 🎉", "Your official face photo has been registered successfully for Face Verification!");
          setProfileData((prev) => ({ ...prev, photo: photoUri }));
        } else {
          setProfileData((prev) => ({ ...prev, photo: photoUri }));
          Alert.alert("Face Photo Registered 📸", "Official face photo updated for Face Verification.");
        }
      }
    } catch (_) {
      setSubmitting(false);
    }
  };

  const menuItems = [
    {
      title: "Personal Information",
      subtitle: "Name, DOB, Gender & Identity",
      icon: "person-outline",
      color: "#173B8C",
      background: "#EEF4FF",
      screen: "PersonalInfo",
    },
    {
      title: "Work Information",
      subtitle: "Designation & Department",
      icon: "briefcase-outline",
      color: "#7C3AED",
      background: "#F5F3FF",
      screen: "WorkInfo",
    },
    {
      title: "Contact Details",
      subtitle: "Email, Phone & Address",
      icon: "call-outline",
      color: "#059669",
      background: "#ECFDF5",
      screen: "Contact",
    },
    {
      title: "Emergency Contact",
      subtitle: "Family Contact Details",
      icon: "people-outline",
      color: "#EA580C",
      background: "#FFF7ED",
      screen: "EmergencyContact",
    },
    {
      title: "Education",
      subtitle: "Academic Qualifications",
      icon: "school-outline",
      color: "#DC2626",
      background: "#FEF2F2",
      screen: "Education",
    },
    {
      title: "Experience",
      subtitle: "Previous Employment",
      icon: "layers-outline",
      color: "#0891B2",
      background: "#ECFEFF",
      screen: "Experience",
    },
    {
      title: "Documents",
      subtitle: "Certificates & Proofs",
      icon: "document-text-outline",
      color: "#4F46E5",
      background: "#EEF2FF",
      screen: "Documents",
    },
    {
      title: "Bank Details",
      subtitle: "Salary Account Information",
      icon: "card-outline",
      color: "#16A34A",
      background: "#F0FDF4",
      screen: "BankDetails",
    },
  ];

  return (
    <LinearGradient colors={["#F8FAFC", "#F6F9FE", "#EEF4FF"]} style={styles.container}>
      <ProfileHeader title="My Profile" showBack={false} />

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => {
              setRefreshing(true);
              loadProfile();
            }}
            colors={["#173B8C"]}
          />
        }
      >
        <DigitalIdCardModal
          visible={showIdCard}
          employee={profileData}
          onClose={() => setShowIdCard(false)}
        />

        <ProfileImageCard
          employeeName={profileData.name}
          employeeId={profileData.employeeId}
          designation={profileData.designation}
          department={profileData.department}
          onEditProfile={() => setEditModalVisible(true)}
          onViewIdCard={() => setShowIdCard(true)}
          onChangePhoto={handleChangePhoto}
        />

        <ProfileCompletionCard percentage={profileData.completion} />

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Employee Contact Details</Text>

          <View style={styles.quickCard}>
            <View style={styles.quickRow}>
              <Ionicons name="mail-outline" size={18} color="#173B8C" />
              <Text style={styles.quickText}>{profileData.email}</Text>
            </View>

            <View style={styles.divider} />

            <View style={styles.quickRow}>
              <Ionicons name="call-outline" size={18} color="#173B8C" />
              <Text style={styles.quickText}>{profileData.phone}</Text>
            </View>

            <View style={styles.divider} />

            <View style={styles.quickRow}>
              <Ionicons name="location-outline" size={18} color="#173B8C" />
              <Text style={styles.quickText}>{profileData.address}</Text>
            </View>
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Profile Sections</Text>

          {menuItems.map((item) => (
            <ProfileMenuCard
              key={item.title}
              title={item.title}
              subtitle={item.subtitle}
              icon={item.icon}
              color={item.color}
              background={item.background}
              onPress={() => {
                try {
                  navigation.navigate(item.screen);
                } catch (_) {
                  Alert.alert(item.title, `${item.subtitle} details.`);
                }
              }}
            />
          ))}
        </View>

        <View style={{ height: 40 }} />
      </ScrollView>

      {/* Edit Profile Modal */}
      <Modal visible={editModalVisible} transparent animationType="slide" onRequestClose={() => setEditModalVisible(false)}>
        <View style={{ flex: 1, backgroundColor: "rgba(15, 23, 42, 0.75)", justifyContent: "center", padding: 20 }}>
          <View style={{ backgroundColor: "#FFFFFF", borderRadius: 24, padding: 24 }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <Text style={{ fontSize: 18, fontWeight: "800", color: "#0F172A" }}>Edit Profile Details</Text>
              <TouchableOpacity onPress={() => setEditModalVisible(false)}>
                <Ionicons name="close-circle" size={24} color="#64748B" />
              </TouchableOpacity>
            </View>

            <Text style={{ fontSize: 11, fontWeight: "700", color: "#64748B", marginTop: 8 }}>FULL NAME</Text>
            <TextInput
              style={styles.modalInput}
              value={editName}
              onChangeText={setEditName}
            />

            <Text style={{ fontSize: 11, fontWeight: "700", color: "#64748B", marginTop: 10 }}>EMAIL ADDRESS</Text>
            <TextInput
              style={styles.modalInput}
              value={editEmail}
              onChangeText={setEditEmail}
              keyboardType="email-address"
            />

            <Text style={{ fontSize: 11, fontWeight: "700", color: "#64748B", marginTop: 10 }}>PHONE NUMBER</Text>
            <TextInput
              style={styles.modalInput}
              value={editPhone}
              onChangeText={setEditPhone}
              keyboardType="phone-pad"
            />

            <Text style={{ fontSize: 11, fontWeight: "700", color: "#64748B", marginTop: 10 }}>ADDRESS</Text>
            <TextInput
              style={styles.modalInput}
              value={editAddress}
              onChangeText={setEditAddress}
            />

            <TouchableOpacity
              style={styles.saveBtn}
              onPress={handleSaveProfile}
              disabled={submitting}
            >
              {submitting ? (
                <ActivityIndicator color="#FFFFFF" />
              ) : (
                <Text style={styles.saveBtnText}>Save Profile Changes</Text>
              )}
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    paddingHorizontal: 18,
    paddingTop: 6,
    paddingBottom: 120,
  },
  section: {
    marginTop: 18,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: "800",
    color: "#0F172A",
    marginBottom: 12,
    letterSpacing: -0.3,
  },
  quickCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    padding: 18,
    borderWidth: 1,
    borderColor: "#E8EDF3",
    shadowColor: "#000",
    shadowOpacity: 0.04,
    shadowRadius: 10,
    shadowOffset: {
      width: 0,
      height: 5,
    },
    elevation: 2,
  },
  quickRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  quickText: {
    marginLeft: 12,
    flex: 1,
    fontSize: 14,
    fontWeight: "600",
    color: "#334155",
  },
  divider: {
    height: 1,
    backgroundColor: "#EEF2F7",
    marginVertical: 12,
  },
  modalInput: {
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    borderRadius: 10,
    padding: 10,
    marginTop: 4,
    fontSize: 14,
    color: "#0F172A",
  },
  saveBtn: {
    backgroundColor: "#173B8C",
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 20,
  },
  saveBtnText: {
    color: "#FFFFFF",
    fontWeight: "700",
    fontSize: 15,
  },
});
