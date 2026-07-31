import React from "react";
import {
  View,
  Text,
  StyleSheet,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";

export default function RatingCard({
  rating,
  score,
  quarter,
  status,
}) {
  const renderStars = () => {
    const stars = [];

    for (let i = 1; i <= 5; i++) {
      stars.push(
        <Ionicons
          key={i}
          name={
            i <= rating
              ? "star"
              : "star-outline"
          }
          size={20}
          color="#F59E0B"
          style={{ marginRight: 3 }}
        />
      );
    }

    return stars;
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Ionicons
          name="stats-chart"
          size={22}
          color="#173B8C"
        />

        <Text style={styles.title}>
          Performance Overview
        </Text>
      </View>

      <View style={styles.ratingRow}>
        <View style={styles.ratingCard}>
          <Text style={styles.label}>
            Overall Rating
          </Text>

          <View style={styles.starRow}>
            {renderStars()}
          </View>

          <Text style={styles.ratingText}>
            {rating}.0 / 5
          </Text>
        </View>

        <View style={styles.scoreCard}>
          <Text style={styles.label}>
            Performance Score
          </Text>

          <Text style={styles.score}>
            {score}%
          </Text>

          <View style={styles.progressBg}>
            <View
              style={[
                styles.progressFill,
                {
                  width: `${score}%`,
                },
              ]}
            />
          </View>
        </View>
      </View>

      <View style={styles.bottomRow}>
        <View style={styles.infoBox}>
          <Text style={styles.smallLabel}>
            Quarter
          </Text>

          <Text style={styles.infoText}>
            {quarter}
          </Text>
        </View>

        <View style={styles.infoBox}>
          <Text style={styles.smallLabel}>
            Review Status
          </Text>

          <View
            style={[
              styles.statusBadge,
              {
                backgroundColor:
                  status === "Completed"
                    ? "#DCFCE7"
                    : "#FEF3C7",
              },
            ]}
          >
            <Text
              style={[
                styles.statusText,
                {
                  color:
                    status === "Completed"
                      ? "#15803D"
                      : "#B45309",
                },
              ]}
            >
              {status}
            </Text>
          </View>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: "#FFFFFF",

    borderRadius: 22,

    padding: 20,

    borderWidth: 1,
    borderColor: "#E8EDF3",

    marginBottom: 22,

    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: {
      width: 0,
      height: 5,
    },

    elevation: 2,
  },

  header: {
    flexDirection: "row",
    alignItems: "center",

    marginBottom: 18,
  },

  title: {
    marginLeft: 10,

    fontSize: 19,

    fontWeight: "800",

    color: "#0F172A",
  },

  ratingRow: {
    flexDirection: "row",
    justifyContent: "space-between",
  },

  ratingCard: {
    flex: 1,
    marginRight: 8,
  },

  scoreCard: {
    flex: 1,
    marginLeft: 8,
  },

  label: {
    fontSize: 13,

    fontWeight: "700",

    color: "#64748B",

    marginBottom: 8,
  },

  starRow: {
    flexDirection: "row",
    marginBottom: 8,
  },

  ratingText: {
    fontSize: 16,

    fontWeight: "800",

    color: "#173B8C",
  },

  score: {
    fontSize: 22,

    fontWeight: "800",

    color: "#173B8C",

    marginBottom: 10,

    letterSpacing: -0.4,
  },

  progressBg: {
    height: 10,

    borderRadius: 10,

    backgroundColor: "#E2E8F0",

    overflow: "hidden",
  },

  progressFill: {
    height: "100%",

    backgroundColor: "#22C55E",

    borderRadius: 10,
  },

  bottomRow: {
    flexDirection: "row",

    marginTop: 22,
  },

  infoBox: {
    flex: 1,
  },

  smallLabel: {
    fontSize: 12,

    color: "#94A3B8",

    fontWeight: "700",

    marginBottom: 6,
  },

  infoText: {
    fontSize: 15,

    fontWeight: "800",

    color: "#173B8C",
  },

  statusBadge: {
    alignSelf: "flex-start",

    paddingHorizontal: 12,
    paddingVertical: 6,

    borderRadius: 20,
  },

  statusText: {
    fontWeight: "800",

    fontSize: 13,
  },
});