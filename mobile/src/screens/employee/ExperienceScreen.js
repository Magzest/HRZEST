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

export default function ExperienceScreen() {
  const [experiences] = useState([]);

  const ExperienceCard = ({ item }) => (
    <View style={styles.card}>
      <View style={styles.topRow}>
        <View style={styles.iconContainer}>
          <Ionicons
            name="briefcase-outline"
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

      <Text style={styles.designation}>
        {item.designation}
      </Text>

      <Text style={styles.company}>
        {item.company}
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
          name="location-outline"
          size={16}
          color="#64748B"
        />

        <Text style={styles.infoText}>
          {item.location}
        </Text>
      </View>

      <View style={styles.badge}>
        <Text style={styles.badgeText}>
          {item.employmentType}
        </Text>
      </View>

      <Text style={styles.description}>
        {item.description}
      </Text>
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <ProfileHeader
        title="Experience"
        showBack
      />

      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        {/* Summary */}

        <View style={styles.summaryCard}>
          <View style={styles.summaryIcon}>
            <Ionicons
              name="briefcase"
              size={32}
              color="#173B8C"
            />
          </View>

          <View style={{ flex: 1, marginLeft: 16 }}>
            <Text style={styles.summaryTitle}>
              Professional Experience
            </Text>

            <Text style={styles.summarySubtitle}>
              Total Experience: {experiences.length > 0 ? "2+ Years" : "0 Years"}
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
          Employment History
        </Text>

        {experiences.map((item) => (
          <ExperienceCard
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
    marginBottom: 24,
    borderWidth: 1,
    borderColor: "#E8EDF3",
    flexDirection: "row",
    alignItems: "center",

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
    backgroundColor: "#F8FAFC",
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

  designation: {
    fontSize: 18,
    fontWeight: "800",
    color: "#0F172A",
  },

  company: {
    fontSize: 15,
    color: "#173B8C",
    fontWeight: "700",
    marginTop: 4,
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
    backgroundColor: "#DCFCE7",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    marginVertical: 14,
  },

  badgeText: {
    color: "#15803D",
    fontWeight: "700",
    fontSize: 12,
  },

  description: {
    fontSize: 14,
    color: "#475569",
    lineHeight: 22,
  },
});