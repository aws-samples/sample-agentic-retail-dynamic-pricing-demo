export interface Product {
  productId: string;
  name: string;
  description: string;
  imageUrl: string;
  category: string;
  subCategory: string;
  currentPrice: number;
  previousPrice: number;
  priceUpdatedAt: string;
  recentlyUpdated: boolean;
  productFamily?: string;
  channels?: string[];
  regions?: string[];
}
