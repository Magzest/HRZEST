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

export default function PersonalInfoScreen() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState({
    employeeId: user?.employeeId || user?.employee_id || "",
    fullName: user?.name || "",
    gender: user?.gender || "Not Specified",
    dob: user?.dob || "Not Specified",
    bloodGroup: user?.blood_group || "Not Specified",
    maritalStatus: "Not Specified",
    nationality: "Not Specified",
    fatherName: "Not Specified",
  });

  useEffect(() => {
    fetchEmployeeProfile()
      .then((res) => {
        if (res?.data?.ok && res?.data?.profile) {
          const p = res.data.profile;
          setProfile({
            employeeId: p.employee_id || user?.employeeId || "",
            fullName: p.name || user?.name || "",
            gender: p.gender || "Not Specified",
            dob: p.dob || "Not Specified",
            bloodGroup: p.blood_group || "Not Specified",
            maritalStatus: p.marital_status || "Not Specified",
            nationality: p.nationality || "Not Specified",
            fatherName: p.father_name || "Not Specified",
          });
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

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
  name: { fontSize: 14, fontWeight: "800", color: "#0F172A" },
  idText: { fontSize: 12, fontWeight: "600", color: "#64748B", marginTop: 2 },
});