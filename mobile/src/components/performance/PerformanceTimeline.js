import React from "react";
import {
  View,
  Text,
  StyleSheet,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";

export default function PerformanceTimeline({
  timeline = [],
}) {
  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Ionicons
          name="time-outline"
          size={22}
          color="#173B8C"
        />

        <Text style={styles.title}>
          Performance Timeline
        </Text>
      </View>

      {timeline.map((item, index) => (
        <View
          key={`${item.quarter}-${item.year || index}`}
          style={[
            styles.row,
            index === timeline.length - 1 && {
              borderBottomWidth: 0,
            },
          ]}
        >
          <View style={styles.left}>
            <View
              style={[
                styles.circle,
                {
                  backgroundColor:
                    item.score >= 90
                      ? "#22C55E"
                      : item.score >= 75
                      ? "#2563EB"
                      : "#F59E0B",
                },
              ]}
            />

            <View style={styles.textContainer}>
              <Text style={styles.quarter}>
                {item.quarter}
              </Text>

              <Text style={styles.year}>
                {item.year}
              </Text>
            </View>
          </View>

          <View style={styles.right}>
            <Text style={styles.score}>
              {item.score}%
            </Text>

            <View style={styles.progressBg}>
              <View
                style={[
                  styles.progressFill,
                  {
                    width: `${item.score}%`,
                    backgroundColor:
                      item.score >= 90
                        ? "#22C55E"
                        : item.score >= 75
                        ? "#2563EB"
                        : "#F59E0B",
                  },
                ]}
              />
            </View>
          </View>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: "#FFFFFF",

    borderRadius: 22,

    padding: 20,

    marginBottom: 22,

    borderWidth: 1,
    borderColor: "#E8EDF3",

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

  row: {
    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",

    paddingVertical: 16,

    borderBottomWidth: 1,

    borderBottomColor: "#EEF2F7",
  },

  left: {
    flexDirection: "row",
    alignItems: "center",

    flex: 1,
  },

  circle: {
    width: 14,
    height: 14,

    borderRadius: 7,

    marginRight: 14,
  },

  textContainer: {
    justifyContent: "center",
  },

  quarter: {
    fontSize: 16,

    fontWeight: "800",

    color: "#0F172A",
  },

  year: {
    marginTop: 3,

    fontSize: 13,

    color: "#64748B",

    fontWeight: "600",
  },

  right: {
    width: 120,
  },

  score: {
    textAlign: "right",

    marginBottom: 8,

    fontSize: 17,

    fontWeight: "800",

    color: "#173B8C",
  },

  progressBg: {
    height: 8,

    backgroundColor: "#E2E8F0",

    borderRadius: 10,

    overflow: "hidden",
  },

  progressFill: {
    height: "100%",

    borderRadius: 10,
  },
});