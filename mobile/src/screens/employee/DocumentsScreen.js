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

export default function DocumentsScreen() {
  const [documents] = useState([]);

  const DocumentCard = ({ item }) => (
    <View style={styles.card}>
      <View style={styles.leftSection}>
        <View style={styles.iconContainer}>
          <Ionicons
            name={item.icon}
            size={26}
            color="#173B8C"
          />
        </View>

        <View style={{ flex: 1 }}>
          <Text style={styles.title}>
            {item.title}
          </Text>

          <Text style={styles.number}>
            {item.number}
          </Text>

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

      <TouchableOpacity style={styles.actionButton}>
        <Ionicons
          name="download-outline"
          size={20}
          color="#173B8C"
        />
      </TouchableOpacity>
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <ProfileHeader
        title="Documents"
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
              name="documents"
              size={32}
              color="#173B8C"
            />
          </View>

          <View style={{ flex: 1, marginLeft: 16 }}>
            <Text style={styles.summaryTitle}>
              Employee Documents
            </Text>

            <Text style={styles.summarySubtitle}>
              {documents.length} Documents Available
            </Text>
          </View>

          <TouchableOpacity style={styles.addButton}>
            <Ionicons
              name="cloud-upload-outline"
              size={22}
              color="#173B8C"
            />
          </TouchableOpacity>
        </View>

        <Text style={styles.sectionTitle}>
          Uploaded Documents
        </Text>

        {documents.map((item) => (
          <DocumentCard
            key={item.id}
            item={item}
          />
        ))}

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
    shadowOffset: {
      width: 0,
      height: 3,
    },

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
});