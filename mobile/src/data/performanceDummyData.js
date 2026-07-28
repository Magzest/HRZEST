const performanceDummyData = {
  header: {
    quarter: "Q3",
    month: "July - September",
    year: 2026,
  },

  summary: {
    totalEmployees: 42,
    reviewsStarted: 31,
    submitted: 24,
    pending: 7,
    averageRating: 4.6,
  },

  analytics: {
    completionRate: 74,
    topPerformer: "John Carter",
    highestRating: 4.9,
    averageKPI: 89,
    incentivesReleased: 18,
  },

  departments: [
    "All Departments",
    "Engineering",
    "Human Resources",
    "Marketing",
    "Finance",
    "Operations",
    "Sales",
    "Support",
  ],

  announcements: [
    {
      id: 1,
      title: "Quarterly Reviews Started",
      description:
        "Managers can now submit Q3 performance reviews.",
      date: "10 Jul",
      priority: "High",
    },
    {
      id: 2,
      title: "New KPI Policy",
      description:
        "Updated KPI calculation is effective from July.",
      date: "06 Jul",
      priority: "Medium",
    },
  ],

  incentives: [
    {
      id: 1,
      employee: "John Carter",
      amount: 12000,
      reason: "Outstanding Performance",
    },
    {
      id: 2,
      employee: "Sarah Wilson",
      amount: 8500,
      reason: "Exceeded Quarterly Targets",
    },
  ],

  employees: [
    {
      id: 1,
      name: "John Carter",
      employeeId: "EMP001",
      designation: "Senior Developer",
      department: "Engineering",

      avatar:
        "JC",

      rating: 4.8,

      kpis: 9,

      completed: true,

      status: "Completed",

      progress: 100,

      incentive: 12000,

      strengths: [
        "Leadership",
        "Ownership",
        "Problem Solving",
      ],
    },

    {
      id: 2,
      name: "Sarah Wilson",
      employeeId: "EMP002",
      designation: "UI Designer",
      department: "Design",

      avatar:
        "SW",

      rating: 4.5,

      kpis: 8,

      completed: true,

      status: "Completed",

      progress: 100,

      incentive: 8500,

      strengths: [
        "Creativity",
        "UX",
        "Teamwork",
      ],
    },

    {
      id: 3,
      name: "Michael Brown",
      employeeId: "EMP003",
      designation: "HR Executive",
      department: "Human Resources",

      avatar:
        "MB",

      rating: 0,

      kpis: 6,

      completed: false,

      status: "Pending",

      progress: 45,

      incentive: 0,

      strengths: [],
    },

    {
      id: 4,
      name: "Emily Davis",
      employeeId: "EMP004",
      designation: "QA Engineer",
      department: "Engineering",

      avatar:
        "ED",

      rating: 4.2,

      kpis: 7,

      completed: true,

      status: "Completed",

      progress: 100,

      incentive: 6000,

      strengths: [
        "Testing",
        "Automation",
      ],
    },

    {
      id: 5,
      name: "David Miller",
      employeeId: "EMP005",
      designation: "Business Analyst",
      department: "Operations",

      avatar:
        "DM",

      rating: 0,

      kpis: 5,

      completed: false,

      status: "Not Started",

      progress: 0,

      incentive: 0,

      strengths: [],
    },
  ],

  chartData: [
    {
      month: "Apr",
      score: 76,
    },
    {
      month: "May",
      score: 81,
    },
    {
      month: "Jun",
      score: 84,
    },
    {
      month: "Jul",
      score: 88,
    },
    {
      month: "Aug",
      score: 91,
    },
    {
      month: "Sep",
      score: 89,
    },
  ],
};

export default performanceDummyData;