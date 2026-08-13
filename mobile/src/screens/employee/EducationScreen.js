import React, { useState } from "react";
import {
  View,
  Text,
 ScrollView,
  StyleSheet,
  TouchableOpacity,
  SafeAreaView,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";

import ProfileHeader from "../../components/profile/ProfileHeader";
import SaveButton from "../../components/profile/SaveButton";

export default function EducationScreen() {
  const [education] = useState([]);

  const EducationCard = ({ item }) => (
    <View style={styles.card}>
      <View style={styles.topRow}>
        <View style={styles.iconContainer}>
          <Ionicons
            name="school-outline"
            size={24}
            color="#173B8C"
          />
        </View>

        <TouchableOpacity style={styles.editButton}>
          <Ionicons
            name="create-outline"
            size={18}
            color="#173B8C"
          />
        </TouchableOpacity>
      </View>

      <Text style={styles.degree}>
        {item.degree}
      </Text>

      <Text style={styles.specialization}>
        {item.specialization}
      </Text>

      <Text style={styles.institution}>
        {item.institution}
      </Text>

      <View style={styles.infoRow}>
        <Ionicons
          name="calendar-outline"
          size={16}
          color="#64748B"
        />
        <Text style={styles.infoText}>
          {item.duration}
        </Text>
      </View>

      <View style={styles.infoRow}>
        <Ionicons
          name="ribbon-outline"
          size={16}
          color="#64748B"
        />
        <Text style={styles.infoText}>
          {item.grade}
        </Text>
      </View>

      <View style={styles.badge}>
        <Text style={styles.badgeText}>
          {item.status}
        </Text>
      </View>
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <ProfileHeader
        title="Education"
        showBack
      />

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
      >
        {/* Summary */}

        <View style={styles.summaryCard}>
          <View style={styles.summaryIcon}>
            <Ionicons
              name="school"
              size={32}
              color="#173B8C"
            />
          </View>

          <View style={{ flex: 1, marginLeft: 16 }}>
            <Text style={styles.summaryTitle}>
              Educational Details
            </Text>

            <Text style={styles.summarySubtitle}>
              {education.length} Qualifications Added
            </Text>
          </View>

          <TouchableOpacity style={styles.addButton}>
            <Ionicons
              name="add"
              size={24}
              color="#173B8C"
            />
          </TouchableOpacity>
        </View>

        <Text style={styles.sectionTitle}>
          Academic Qualifications
        </Text>

        {education.map((item) => (
          <EducationCard
            key={item.id}
            item={item}
          />
        ))}

        <SaveButton
          title="Save Changes"
          onPress={() => {}}
        />

        <View style={{ height: 40 }} />
      </ScrollView>
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
    paddingBottom: 120,
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
    shadowOffset: {
      width: 0,
      height: 5,
    },

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
    backgroundColor: "#F8FAFC",
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
    padding: 18,
    marginBottom: 18,
    borderWidth: 1,
    borderColor: "#E8EDF3",

    shadowColor: "#0F172A",
    shadowOpacity: 0.04,
    shadowRadius: 8,
    shadowOffset: {
      width: 0,
      height: 4,
    },

    elevation: 2,
  },

  topRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 14,
  },

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

  degree: {
    fontSize: 14,
    fontWeight: "800",
    color: "#0F172A",
  },

  specialization: {
    marginTop: 4,
    fontSize: 13,
    color: "#173B8C",
    fontWeight: "700",
  },

  institution: {
    marginTop: 6,
    fontSize: 14,
    color: "#475569",
    marginBottom: 12,
  },

  infoRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 8,
  },

  infoText: {
    marginLeft: 8,
    fontSize: 14,
    color: "#64748B",
    fontWeight: "500",
  },

  badge: {
    alignSelf: "flex-start",
    marginTop: 14,
    backgroundColor: "#DCFCE7",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
  },

  badgeText: {
    color: "#15803D",
    fontSize: 12,
    fontWeight: "700",
  },
});